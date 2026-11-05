// Phrase Countdown Light firmware.
//
// The laptop (Set Prep Copilot) owns all timing: it tracks the decks from the
// FLX4's MIDI and sends one line over USB serial, 10 times a second, saying how
// far away the next cue is. This board only draws that on a 16-LED ring:
// each LED is half a bar, so a full ring is the last 8 bars before the cue.
//
// Protocol (one ASCII line each, '\n' terminated):
//   laptop -> board   ?                                  who are you?
//                     C <ms_to_cue> <ms_per_beat> <rrggbb>  next cue
//                     I                                  idle, nothing to show
//                     B <0-255>                          brightness, saved to flash
//   board -> laptop   HELLO pcl 1                        on boot and in reply to ?
//                     K <0-255>                          SW1 changed the brightness
//                     ERR <line>                         line not understood
//
// Hardware: XIAO ESP32C3. D10 (GPIO10) -> SN74AHCT125 gate 1 -> 330 ohm -> ring
// DIN. D1 (GPIO3) -> SW1 -> GND. GPIO2/8/9 are boot strapping pins, so avoided.

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <Preferences.h>

// ---- Hardware -------------------------------------------------------------
constexpr uint8_t PIN_LED = 10;    // XIAO D10 = GPIO10
constexpr uint8_t PIN_BUTTON = 3;  // XIAO D1 = GPIO3, internal pull-up
constexpr uint8_t NUM_LEDS = 16;

// Which physical LED sits at 12 o'clock, and whether index order runs
// clockwise when the ring is mounted. Adjust after the first build.
constexpr uint8_t RING_TOP = 0;
constexpr bool RING_CLOCKWISE = true;

// ---- Power ----------------------------------------------------------------
// Worldsemi's WS2812B datasheet lists 16 mA per color channel; 20 mA is the
// usual conservative design figure, used here so the estimate errs high.
constexpr float MA_PER_CHANNEL = 20.0f;
// USB 2.0: 100 mA until the host configures the device, 500 mA after (the
// C3's fixed USB descriptor asks for 500 mA). Budget once configured:
// 300 mA LEDs + ~16 mA ring idle + 28 mA ESP32-C3 + ~1.5 mA AHCT125 ~= 346 mA.
// Before that, the ring stays dark: ~46 mA total, under the 100 mA limit.
constexpr float LED_BUDGET_MA = 300.0f;
// The C3's USB Serial/JTAG is fixed-function hardware, so firmware can't see
// the host's SET_CONFIGURATION. Treat USB as configured once the host has
// sent SOF frames for this long (enumeration takes well under a second), or
// as soon as the CDC link carries data, which needs a configured device.
constexpr uint32_t USB_SETTLE_MS = 1000;

// ---- Behavior -------------------------------------------------------------
constexpr uint32_t LINK_TIMEOUT_MS = 2000;
constexpr uint32_t FRAME_MS = 16;  // ~60 fps
constexpr uint8_t DEFAULT_BRIGHTNESS = 102;  // 40%
constexpr uint8_t BRIGHTNESS_STEPS[] = {26, 51, 102, 153, 204, 255};
constexpr uint8_t STATUS_LEVEL = 12;  // the single dim "connected" LED

Adafruit_NeoPixel ring(NUM_LEDS, PIN_LED, NEO_GRB + NEO_KHZ800);
Preferences prefs;

enum class Mode { Idle, Countdown };

struct State {
  Mode mode = Mode::Idle;
  uint32_t cueAt = 0;        // millis() when the cue lands
  uint32_t msPerBeat = 500;
  uint8_t r = 0, g = 0, b = 0;
  uint32_t lastLineAt = 0;
  bool everHeard = false;
  bool usbReady = false;     // latched: host has configured the USB device
  bool selfTestPending = false;
  uint8_t brightness = DEFAULT_BRIGHTNESS;
} state;

// Per-frame working buffer, as floats so scaling happens once at the end.
float frameR[NUM_LEDS], frameG[NUM_LEDS], frameB[NUM_LEDS];

// ---------------------------------------------------------------------------

uint16_t physical(uint8_t logical) {
  // logical 0 = 12 o'clock, increasing clockwise
  int16_t idx = RING_CLOCKWISE ? RING_TOP + logical : RING_TOP - logical;
  return (uint16_t)((idx % NUM_LEDS + NUM_LEDS) % NUM_LEDS);
}

void clearFrame() {
  for (uint8_t i = 0; i < NUM_LEDS; i++) frameR[i] = frameG[i] = frameB[i] = 0;
}

void setLogical(uint8_t i, float r, float g, float b) {
  frameR[i] = max(frameR[i], r);
  frameG[i] = max(frameG[i], g);
  frameB[i] = max(frameB[i], b);
}

// Estimate the ring's current and scale the whole frame down to the budget,
// then push it out.
void showFrame() {
  float ma = 0;
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    ma += (frameR[i] + frameG[i] + frameB[i]) / 255.0f * MA_PER_CHANNEL;
  }
  float scale = ma > LED_BUDGET_MA ? LED_BUDGET_MA / ma : 1.0f;
  for (uint8_t i = 0; i < NUM_LEDS; i++) {
    ring.setPixelColor(physical(i),
                       (uint8_t)constrain(frameR[i] * scale, 0, 255),
                       (uint8_t)constrain(frameG[i] * scale, 0, 255),
                       (uint8_t)constrain(frameB[i] * scale, 0, 255));
  }
  ring.show();
}

// ---- Rendering --------------------------------------------------------------

void drawStatusDot() {
  setLogical(0, STATUS_LEVEL, STATUS_LEVEL, STATUS_LEVEL);
}

void drawLinkLost(uint32_t now) {
  // Slow dim white breathing, 3 s period.
  float phase = (now % 3000) / 3000.0f;
  float level = 4 + 20 * (0.5f - 0.5f * cosf(phase * 2 * PI));
  for (uint8_t i = 0; i < NUM_LEDS; i++) setLogical(i, level, level, level);
}

void drawCountdown(uint32_t now) {
  const int32_t remaining = (int32_t)(state.cueAt - now);  // wrap-safe
  const float beat = state.msPerBeat;
  const float halfBar = 2 * beat, bar = 4 * beat;
  const float k = state.brightness / 255.0f;
  const float r = state.r, g = state.g, b = state.b;

  if (remaining > 8 * bar) {  // too far out: just show we're connected
    drawStatusDot();
    return;
  }
  if (remaining > 0) {
    // One LED per half bar left, emptying clockwise from 12 o'clock.
    uint8_t lit = (uint8_t)min<float>(NUM_LEDS, ceilf(remaining / halfBar));
    for (uint8_t i = NUM_LEDS - lit; i < NUM_LEDS; i++) setLogical(i, r * k, g * k, b * k);
    if (remaining <= bar) {
      // Last bar: whole ring pulses on each beat (4, 3, 2, 1).
      float sinceBeat = fmodf(beat - fmodf(remaining, beat), beat);
      float pulse = 1.0f - sinceBeat / beat;
      pulse = 0.35f * pulse * pulse;
      for (uint8_t i = 0; i < NUM_LEDS; i++) setLogical(i, r * k * pulse, g * k * pulse, b * k * pulse);
    }
    return;
  }
  const float after = -remaining;
  if (after < beat) {  // the cue itself: full flash, still under the current cap
    for (uint8_t i = 0; i < NUM_LEDS; i++) setLogical(i, r, g, b);
    return;
  }
  if (after < beat + bar) {  // fade out over the next bar
    float f = 1.0f - (after - beat) / bar;
    for (uint8_t i = 0; i < NUM_LEDS; i++) setLogical(i, r * f, g * f, b * f);
    return;
  }
  drawStatusDot();  // waiting for the next C line
}

void render(uint32_t now) {
  clearFrame();
  if (!state.everHeard || now - state.lastLineAt > LINK_TIMEOUT_MS) {
    drawLinkLost(now);
  } else if (state.mode == Mode::Countdown) {
    drawCountdown(now);
  } else {
    drawStatusDot();
  }
  showFrame();
}

// ---- Brightness -------------------------------------------------------------

void setBrightness(uint8_t value, bool announce) {
  state.brightness = value;
  prefs.putUChar("bright", value);
  if (announce) {
    Serial.print("K ");
    Serial.println(value);
  }
}

void nextBrightnessStep() {
  const size_t n = sizeof(BRIGHTNESS_STEPS);
  size_t i = 0;
  while (i < n && BRIGHTNESS_STEPS[i] <= state.brightness) i++;
  setBrightness(BRIGHTNESS_STEPS[i % n], true);
}

// ---- Serial protocol --------------------------------------------------------

void sayHello() { Serial.println("HELLO pcl 1"); }

void reject(const char* line) {
  Serial.print("ERR ");
  Serial.println(line);
}

bool parseHexColor(const char* s, uint8_t& r, uint8_t& g, uint8_t& b) {
  if (strlen(s) != 6) return false;
  for (uint8_t i = 0; i < 6; i++) {
    if (!isxdigit((unsigned char)s[i])) return false;
  }
  uint32_t v = strtoul(s, nullptr, 16);
  r = (v >> 16) & 0xFF;
  g = (v >> 8) & 0xFF;
  b = v & 0xFF;
  return true;
}

void handleLine(char* line, uint32_t now) {
  if (line[0] == '\0') return;

  if (strcmp(line, "?") == 0) {
    sayHello();
  } else if (strcmp(line, "I") == 0) {
    state.mode = Mode::Idle;
  } else if (line[0] == 'C' && line[1] == ' ') {
    char hex[8] = {0};
    long msToCue = 0, msPerBeat = 0;
    uint8_t r, g, b;
    if (sscanf(line + 2, "%ld %ld %7s", &msToCue, &msPerBeat, hex) != 3 ||
        msPerBeat < 100 || msPerBeat > 2000 || !parseHexColor(hex, r, g, b)) {
      reject(line);
      return;
    }
    state.mode = Mode::Countdown;
    state.cueAt = now + (uint32_t)(int32_t)msToCue;
    state.msPerBeat = (uint32_t)msPerBeat;
    state.r = r;
    state.g = g;
    state.b = b;
  } else if (line[0] == 'B' && line[1] == ' ') {
    long v = strtol(line + 2, nullptr, 10);
    if (v < 0 || v > 255) {
      reject(line);
      return;
    }
    setBrightness((uint8_t)v, false);
  } else {
    reject(line);
    return;
  }
  state.lastLineAt = now;
  state.everHeard = true;
}

void pollSerial(uint32_t now) {
  static char buf[64];
  static uint8_t len = 0;
  static bool overflow = false;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      buf[len] = '\0';
      if (!overflow) handleLine(buf, now);
      len = 0;
      overflow = false;
    } else if (len < sizeof(buf) - 1) {
      buf[len++] = c;
    } else {
      overflow = true;  // drop the whole over-long line
    }
  }
}

// ---- Button -----------------------------------------------------------------

void pollButton(uint32_t now) {
  static bool lastStable = HIGH, lastRead = HIGH;
  static uint32_t changedAt = 0;
  bool reading = digitalRead(PIN_BUTTON);
  if (reading != lastRead) {
    lastRead = reading;
    changedAt = now;
  }
  if (now - changedAt > 30 && reading != lastStable) {
    lastStable = reading;
    if (lastStable == LOW) nextBrightnessStep();  // pressed
  }
}

// ---- Self-test (hold SW1 at power-up) ---------------------------------------

void selfTest() {
  const uint8_t colors[3][3] = {{255, 0, 0}, {0, 255, 0}, {0, 0, 255}};
  for (const auto& c : colors) {
    for (uint8_t i = 0; i < NUM_LEDS; i++) {  // walk one LED round the ring
      clearFrame();
      setLogical(i, c[0], c[1], c[2]);
      showFrame();
      delay(60);
    }
    clearFrame();  // then the whole ring, current-capped
    for (uint8_t i = 0; i < NUM_LEDS; i++) setLogical(i, c[0], c[1], c[2]);
    showFrame();
    delay(500);
  }
  clearFrame();
  showFrame();
}

// ---------------------------------------------------------------------------

void setup() {
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  Serial.begin(115200);  // native USB CDC; the baud rate is ignored

  prefs.begin("pcl", false);
  state.brightness = prefs.getUChar("bright", DEFAULT_BRIGHTNESS);

  ring.begin();
  ring.clear();
  ring.show();

  // SW1 held at power-up: remember it, run the test once USB is configured.
  state.selfTestPending = digitalRead(PIN_BUTTON) == LOW;

  sayHello();  // may be missed if no host is listening yet; the host asks with ?
}

// Latches true once the host has configured us (see USB_SETTLE_MS). Until
// then the ring stays dark, keeping the board under USB's 100 mA limit.
bool pollUsbReady(uint32_t now) {
  static uint32_t pluggedSince = 0;
  static bool wasPlugged = false;
  if (state.usbReady) return true;
  bool plugged = HWCDC::isPlugged();  // host is sending SOF frames
  if (plugged && !wasPlugged) pluggedSince = now;
  wasPlugged = plugged;
  if ((plugged && now - pluggedSince >= USB_SETTLE_MS) || Serial || state.everHeard) {
    state.usbReady = true;
  }
  return state.usbReady;
}

void loop() {
  static uint32_t lastFrame = 0;
  uint32_t now = millis();
  pollSerial(now);
  if (!pollUsbReady(now)) return;  // ring was cleared in setup() and stays dark
  if (state.selfTestPending) {
    state.selfTestPending = false;
    selfTest();
    now = millis();
  }
  pollButton(now);
  if (now - lastFrame >= FRAME_MS) {
    lastFrame = now;
    render(now);
  }
}
