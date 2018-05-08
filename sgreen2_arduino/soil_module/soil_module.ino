#include <RF24.h>

#include "SoftwareSerial.h"
#include "LowPower.h"

#define SLEEP_TIME_SECONDS 120 //Sleep for 120 seconds

#define SOIL_MOISTURE_DATA_PIN A0
#define SOIL_MOISTURE_ENABLE_PIN 7
#define SOIL_MOISTURE_GROUND_PIN 8

#define VOLTAGE_READING_PIN A3
float resistor1 = 5100; //you can change it if you want, just make sure you also do it on the circuit
float resistor2 = 5600;
float Vmax = (3.19*resistor1 + 3.19*resistor2)/resistor2;

#define ID "03"
#define SOIL_TYPE "soil"
#define SOIL_ID SOIL_TYPE ID
#define SOIL_UNIT "soil_raw"
#define BATTERY_TYPE "batt"
#define BATTERY_ID BATTERY_TYPE ID
#define BATTERY_UNIT "batt_volts"

//13 - SCK, 12 - MISO, 11 - MOSI
#define RF24_CE_PIN 9
#define RF24_CS_PIN 10
RF24 radio(RF24_CE_PIN, RF24_CS_PIN);

const uint64_t pipe01 = 0xE8E8F0F0A1LL;
const uint64_t pipe02 = 0xE8E8F0F0A2LL;  
const uint64_t pipe03 = 0xE8E8F0F0A3LL;
const uint64_t pipe04 = 0xE8E8F0F0A4LL;
const uint64_t pipe05 = 0xE8E8F0F0A5LL;
//const uint64_t pipe06 = 0xE8E8F0F0A6LL;

uint64_t setPipeToSend = pipe03; // or pipe02 or pipe03 or pipe04 or pipe05

struct payload_t {
  char id[3];
  uint16_t soil_moisture_reading;
  float voltage_reading;
};

void setup() {
  // put your setup code here, to run once:
  pinMode(VOLTAGE_READING_PIN, INPUT);
  pinMode(SOIL_MOISTURE_ENABLE_PIN, OUTPUT);
  pinMode(SOIL_MOISTURE_GROUND_PIN, OUTPUT);
  digitalWrite(SOIL_MOISTURE_GROUND_PIN, LOW);
  pinMode(SOIL_MOISTURE_DATA_PIN, INPUT);
  Serial.begin(9600);
  Serial.println("Starting"); 
  radio.begin();
  radio.openWritingPipe(setPipeToSend);
  radio.setPALevel(RF24_PA_MAX);
  radio.stopListening();
}

void loop() {
  digitalWrite(SOIL_MOISTURE_ENABLE_PIN, HIGH);
  delay(100);
  int soil_moisture_reading = analogRead(SOIL_MOISTURE_DATA_PIN);
  digitalWrite(SOIL_MOISTURE_ENABLE_PIN, LOW);
  float voltage_reading = analogRead(VOLTAGE_READING_PIN) * Vmax/1024;
  payload_t payload;
  memcpy(payload.id, ID, sizeof(payload.id));
  payload.soil_moisture_reading = soil_moisture_reading;
  Serial.println(voltage_reading);
  payload.voltage_reading = voltage_reading;
  radio.powerUp();
  delay(100);
  Serial.println("WRITING");
  radio.write(&payload, sizeof(payload));
  Serial.println("WROTE");
  radio.powerDown(); 
  /*SLEEP MODE*/
  int timer = 0;
  while(timer <= SLEEP_TIME_SECONDS){
    LowPower.powerDown(SLEEP_8S, ADC_OFF, BOD_OFF); //sleeps for 8 seconds. 8 is the max.
    timer += 8;  
  }
}
