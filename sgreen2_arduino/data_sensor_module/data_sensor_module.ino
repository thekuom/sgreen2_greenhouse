#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

#include "src/libs/FanMonitor.h"
#include "src/libs/DHT.h"

//Define parameters for the temperature sensor
#define DHTTYPE DHT22   // DHT 22  (AM2302), AM2321
#define DHT_01_VCC_PIN 7
#define DHT_01_PIN 6
#define DHT_01_GROUND_PIN 5
#define DHT_02_VCC_PIN 4
#define DHT_02_PIN 3
#define DHT_02_GROUND_PIN 2
DHT dht_01(DHT_01_PIN, DHTTYPE);
DHT dht_02(DHT_02_PIN, DHTTYPE);

//Define parameters for fan sensor
#define FAN_MONITOR_PIN_01 A0
#define FAN_MONITOR_PIN_03 A2
#define FAN_VCC_PIN 8
FanMonitor fan_monitor_01 = FanMonitor(FAN_MONITOR_PIN_01, FAN_TYPE_UNIPOLE);
FanMonitor fan_monitor_03 = FanMonitor(FAN_MONITOR_PIN_03, FAN_TYPE_UNIPOLE);

//Define parameters for NRF24L01
//Note, using SPI communication (13 - SCK, 11 - MOSI, 12 - MISO)
#define RF24_CE_PIN 9
#define RF24_CS_PIN 10
RF24 radio(RF24_CE_PIN, RF24_CS_PIN);
//Supports up to 6 pipes for reading
//To add more pipe, use the RF24 Mesh + Network libraries
//const byte addresses[][6] = {"00001","00002","00003","00004","00005"};

const char *data_mask = "{\"sensor\": {\"type\": \"%s\", \"name\": \"%s\"}, \"reading\":%s, \"unit\":\"%s\"}";
#define TEMPERATURE_TYPE "temp"
#define TEMPERATURE_ID_01 TEMPERATURE_TYPE"01"
#define TEMPERATURE_ID_02 TEMPERATURE_TYPE"02"
#define TEMPERATURE_UNIT "temp_f"
#define HUMIDITY_TYPE "humid"
#define HUMIDITY_ID_01 HUMIDITY_TYPE"01"
#define HUMIDITY_ID_02 HUMIDITY_TYPE"02"
#define HUMIDITY_UNIT "humid_percent"
#define FAN_TYPE "fanspeed"
#define FAN_ID_01 "fan01"
#define FAN_ID_03 "fan03"
#define FANSPEED_UNIT "fanspeed_rpm"
#define SOIL_TYPE "soil"
#define SOIL_UNIT "soil_raw"
#define BATTERY_TYPE "batt"
#define BATTERY_UNIT "batt_volts"

char temperature_01_data[100];
char temperature_02_data[100];
char humidity_01_data[100];
char humidity_02_data[100];
char fan_01_data[100];
char fan_03_data[100];
char soil_moisture_data[100];
char voltage_reading_data[100];

const uint64_t pipe01 = 0xE8E8F0F0A1LL;
const uint64_t pipe02 = 0xA2LL;  
const uint64_t pipe03 = 0xA3LL;
const uint64_t pipe04 = 0xA4LL;
const uint64_t pipe05 = 0xA5LL;
const uint64_t pipe06 = 0xA6LL;

struct payload_t {
  char id[3];
  uint16_t soil_moisture_reading;
  float voltage_reading;
};

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  pinMode(FAN_VCC_PIN, OUTPUT);
  pinMode(DHT_01_VCC_PIN, OUTPUT);
  pinMode(DHT_02_VCC_PIN, OUTPUT);
  pinMode(DHT_01_GROUND_PIN, OUTPUT);
  pinMode(DHT_02_GROUND_PIN, OUTPUT);
  digitalWrite(DHT_01_GROUND_PIN, LOW);
  digitalWrite(DHT_02_GROUND_PIN, LOW);

  fan_monitor_01.begin();
  fan_monitor_03.begin();
  dht_01.begin();
  dht_02.begin();

  radio.begin();
  radio.openReadingPipe(1, pipe01);
  radio.openReadingPipe(2, pipe02);
  radio.openReadingPipe(3, pipe03);
  radio.openReadingPipe(4, pipe04);
  radio.openReadingPipe(5, pipe05);
  radio.setPALevel(RF24_PA_MAX);
  radio.startListening();
 }

void loop() {
  // put your main code here, to run repeatedly:
  // Measure fan speeds
  digitalWrite(FAN_VCC_PIN, HIGH);
  delay(1000);
  uint16_t fan_speed_01 = fan_monitor_01.getSpeed();
  delay(1000);
  uint16_t fan_speed_03 = fan_monitor_03.getSpeed();
  digitalWrite(FAN_VCC_PIN, LOW);
  // Send fan data
  sprintf(fan_01_data, data_mask, FAN_TYPE, FAN_ID_01, String(fan_speed_01).c_str(), FANSPEED_UNIT);
  Serial.println(fan_01_data);
  sprintf(fan_03_data, data_mask, FAN_TYPE, FAN_ID_03, String(fan_speed_03).c_str(), FANSPEED_UNIT);
  Serial.println(fan_03_data);
  //Read humidity
  digitalWrite(DHT_01_VCC_PIN, HIGH);
  digitalWrite(DHT_02_VCC_PIN, HIGH);
  delay(2000);
  float humidity_01 = dht_01.readHumidity();
  float humidity_02 = dht_02.readHumidity();
  // Read temperature as Fahrenheit (isFahrenheit = true)
  float temperature_01 = dht_01.readTemperature(true);
  float temperature_02 = dht_02.readTemperature(true);
  digitalWrite(DHT_01_VCC_PIN, LOW);
  digitalWrite(DHT_02_VCC_PIN, LOW);
  //Send temperature and humidity data for sensor 1
  if(!(isnan(humidity_01) || isnan(temperature_01))){
    sprintf(temperature_01_data, data_mask, TEMPERATURE_TYPE, TEMPERATURE_ID_01, String(temperature_01).c_str(), TEMPERATURE_UNIT);
    Serial.println(temperature_01_data);
    sprintf(humidity_01_data, data_mask, HUMIDITY_TYPE, HUMIDITY_ID_01, String(humidity_01).c_str(), HUMIDITY_UNIT);
    Serial.println(humidity_01_data);
  }
  //Send temperatue and humidity data for sensor 2
  if(!(isnan(humidity_02) || isnan(temperature_02))){
    sprintf(temperature_02_data, data_mask, TEMPERATURE_TYPE, TEMPERATURE_ID_02, String(temperature_02).c_str(), TEMPERATURE_UNIT);
    Serial.println(temperature_02_data);
    sprintf(humidity_02_data, data_mask, HUMIDITY_TYPE, HUMIDITY_ID_02, String(humidity_02).c_str(), HUMIDITY_UNIT);
    Serial.println(humidity_02_data);
  }
  //Read data transmitted to RF24 module
  while(radio.available()){
    payload_t payload;
    radio.read(&payload, sizeof(payload));
//    radio.flush_rx();
    String soil_id = String(SOIL_TYPE) + String(payload.id);
    String battery_id = String(BATTERY_TYPE) + String(payload.id);
    sprintf(soil_moisture_data, data_mask, SOIL_TYPE, soil_id.c_str(), String(payload.soil_moisture_reading).c_str(), SOIL_UNIT);
    Serial.println(soil_moisture_data);
    sprintf(voltage_reading_data, data_mask, BATTERY_TYPE, battery_id.c_str(), String(payload.voltage_reading).c_str(), BATTERY_UNIT);
    Serial.println(voltage_reading_data);
  }
//  for(int i=0; i < sizeof(addresses)/sizeof(addresses[0]); ++i){
//    if(radio.available()){
//      payload_t payload;
//      radio.read(&payload, sizeof(payload));
//      String soil_id = String(SOIL_TYPE) + String(payload.id);
//      String battery_id = String(BATTERY_TYPE) + String(payload.id);
//      sprintf(soil_moisture_data, data_mask, SOIL_TYPE, soil_id.c_str(), String(payload.soil_moisture_reading).c_str(), SOIL_UNIT);
//      Serial.println(soil_moisture_data);
//      sprintf(voltage_reading_data, data_mask, BATTERY_TYPE, battery_id.c_str(), String(payload.voltage_reading).c_str(), BATTERY_UNIT);
//      Serial.println(voltage_reading_data);
//    }
//  }
  delay(1000);
}
