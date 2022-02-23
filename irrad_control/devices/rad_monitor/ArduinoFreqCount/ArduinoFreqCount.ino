#include <FreqCount.h>


unsigned int sample_time = 1000;  // Time window in which pulses are counted in ms
const char operations[] = {'s', 'g', 'x'};  // Start, Get and Stop operations
const char properties[] = {'t', 'f', 'c'};  // Properties on which at least one operation is valid; Time and Frequency
unsigned int current_int; // Stores a parsed integer
unsigned long current_count;  // Store counts
unsigned long current_freq;  // Store frequency
String cmd_string;  // Declare command string


unsigned long frequency(unsigned long counts, unsigned int s_time) {
  float scale = (float)1000 / (float)s_time;
  return counts * scale;
}


void failure() {
  Serial.println(-1);
}


void test() {
  Serial.println(1);
}

void write_res(unsigned long res) {
  Serial.println(res);  // Write result
  delayMicroseconds(50);  // Wait a little bit
}


void setup() {
  Serial.begin(9600);
  delay(1000);  // Wait for Serial setup
  FreqCount.begin(sample_time);
}


void loop() {

  // Check if something is being send
  if(Serial.available()) {

    // Read entire command at once (until new line), this waits until timeout (defaults to 1000 ms)
    cmd_string = Serial.readStringUntil('\n');

    // We're setting sth
    if(cmd_string[0] == operations[0]) {
      // Setting the sampling time
      if(cmd_string[1] == properties[0]) {
        // Remaining characters in queue are sampling time
        current_int = cmd_string.substring(2).toInt();
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
    else if(cmd_string[0] == operations[1]) {
      // Getting the sampling time
      if(cmd_string[1] == properties[0]) {
        write_res(sample_time);
      } 
      // Getting the Frequency
      else if(cmd_string[1] == properties[1]) {

        if(FreqCount.available()){
          current_count = FreqCount.read();
          current_freq = frequency(current_count, sample_time);
          write_res(current_freq);
        }
      }
      // Getting the counts
      else if(cmd_string[1] == properties[2]) {

        if(FreqCount.available()){
          current_count = FreqCount.read();
          write_res(current_count);
        }
      }
    }
    // We're stopping the frequency reading
    else if(cmd_string[0] == operations[2]) {
      FreqCount.end();
    }
    // We're testing the connection
    else if(cmd_string[0] == 't') {
      test();
    }
    else {
      failure();
    }
  }
}