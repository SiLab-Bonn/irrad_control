#include <FreqCount.h>


unsigned int sample_time = 1000;  // Time window in which pulses are counted in ms
const char operations[] = {'S', 'G', 'X'};  // Start, Get and Stop operations
const char properties[] = {'T', 'F', 'C'};  // Properties on which at least one operation is valid; Time ,Frequency and Raw Counts
char current_char;  // Stores the incoming character
unsigned int current_int; // Stores a parsed integer
unsigned long current_count;  // Store counts
unsigned long current_freq;  // Store frequency


unsigned long frequency(unsigned long counts, unsigned int s_time) {
  float scale = (float)1000 / (float)s_time;  // cast to float in order to scale correctly before integer cast
  return counts * scale;
}

void failure() {
  Serial.println(-1);
}


void setup() {
  Serial.begin(9600);
  FreqCount.begin(sample_time);
}

void loop() {

  // Check if something is being send
  if(Serial.available(){
    // Check whether sth needs to be set or getting
    current_char = Serial.read();

    // We're setting sth
    if(current_char == operations[0]) {

      current_char = Serial.read();

      // Setting the sampling time
      if(current_char == properties[0]) {
        // Remaining characters in queue are sampling time
        current_int = Serial.parseInt();
        if(current_int < 0){
          failure();
        }
        else {
          sample_time = current_int;
          FreqCount.begin(sample_time);
        }
      }
    }
    // We're getting something
    else if(current_char == operations[1]) {

      current_char = Serial.read();

      // Getting the sampling time
      if(current_char == properties[0]) {
        Serial.println(sample_time);
      }
      else if(current_char == properties[1]) {

        if(FreqCount.available()){
          current_count = FreqCount.read();
          current_freq = frequency(current_count, sample_time);
          Serial.println(current_freq);
        }
      }
      else if(current_char == properties[2]) {

        if(FreqCount.available()){
          current_count = FreqCount.read();
          Serial.println(current_count);
        }
      }
    }
    // We're stopping the frequency reading
    else if(current_char == operations[2]) {
      FreqCount.end();
    }

    else {
      failure();
    }
  }
