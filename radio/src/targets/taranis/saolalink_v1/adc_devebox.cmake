# Derive DevEBox inputs; preserve the Pocket-compatible source JSON.
set(_adc_base "${RADIO_SRC_DIR}/boards/hw_defs/saolalinkv1.json")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_adc_base}")
file(READ "${_adc_base}" _adc_json)
string(JSON _adc_count LENGTH "${_adc_json}" adc_inputs inputs)
math(EXPR _adc_last "${_adc_count} - 1")
foreach(_idx RANGE 0 ${_adc_last})
  string(JSON _name GET "${_adc_json}" adc_inputs inputs ${_idx} name)
  if(_name STREQUAL "RV" OR _name STREQUAL "RH")
    if(_name STREQUAL "RV")
      set(_pin 1)
      set(_channel 11)
    else()
      set(_pin 2)
      set(_channel 12)
    endif()
    string(JSON _adc_json SET "${_adc_json}" adc_inputs inputs ${_idx} gpio "\"GPIOC\"")
    string(JSON _adc_json SET "${_adc_json}" adc_inputs inputs ${_idx} pin "\"LL_GPIO_PIN_${_pin}\"")
    string(JSON _adc_json SET "${_adc_json}" adc_inputs inputs ${_idx} channel "\"LL_ADC_CHANNEL_${_channel}\"")
  endif()
endforeach()

# Keep all FLEX inputs contiguous before battery channels. Both the HAL input
# offsets and the STM32 DMA sequence must use this same description.
foreach(_idx RANGE ${_adc_last} 5 -1)
  string(JSON _input GET "${_adc_json}" adc_inputs inputs ${_idx})
  math(EXPR _dest "${_idx} + 1")
  string(JSON _adc_json SET "${_adc_json}" adc_inputs inputs ${_dest} "${_input}")
endforeach()
string(JSON _adc_json SET "${_adc_json}" adc_inputs inputs 5 [=[{
  "name": "P2", "type": "FLEX", "adc": "MAIN",
  "gpio": "GPIOA", "pin": "LL_GPIO_PIN_6", "channel": "LL_ADC_CHANNEL_6",
  "inverted": false, "label": "S2", "short_label": "2", "default": "POT"
}]=])

string(JSON _switch_count LENGTH "${_adc_json}" switches)
math(EXPR _switch_last "${_switch_count} - 1")
foreach(_idx RANGE ${_switch_last} 0 -1)
  string(JSON _name GET "${_adc_json}" switches ${_idx} name)
  if(_name STREQUAL "SE")
    # SE was replaced physically by S2. PE7 is no longer a switch input.
    string(JSON _adc_json REMOVE "${_adc_json}" switches ${_idx})
  elseif(_name STREQUAL "SC")
    string(JSON _adc_json SET "${_adc_json}" switches ${_idx} type "\"2POS\"")
    string(JSON _adc_json SET "${_adc_json}" switches ${_idx} default "\"2POS\"")
    string(JSON _adc_json SET "${_adc_json}" switches ${_idx} gpio "\"GPIOD\"")
    string(JSON _adc_json SET "${_adc_json}" switches ${_idx} pin "\"LL_GPIO_PIN_11\"")
    foreach(_field gpio_high pin_high gpio_low pin_low)
      string(JSON _adc_json REMOVE "${_adc_json}" switches ${_idx} ${_field})
    endforeach()
  endif()
endforeach()
set(ADC_HW_DESC_JSON "${CMAKE_CURRENT_BINARY_DIR}/saolalink-devebox-adc.json")
file(CONFIGURE OUTPUT "${ADC_HW_DESC_JSON}" CONTENT "${_adc_json}\n" @ONLY)
