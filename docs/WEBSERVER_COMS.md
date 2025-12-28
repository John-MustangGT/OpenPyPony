# ESP-01s Webserver rewrite

## Overview
- state machine on both ends
- the tokens are always bracketed with Newlines, eg. "\nESP-01:Ready\n"
- UART runs at 115200
- UART buffer 4k

## Communcations

### ESP-01s end

- **Configuration State**
  - Boots up and sends "ESP:config"
  - Logger replies with-
    - "OPL:config-start"
    - "mode=AP"
    - "ip=192.168.4.2"
    - "gw=192.168.4.1"
    - "subnet=255.255.255.0"
    - "ssid=OpenPonyLogger"
    - "password=mustanggt"
    - "OPL:config-end
  - if everything is good it moves to Serving else it resets
- **Serving State**
  - On client GET
    - "ESP:get-start"
    - "ESP:get-end"
    

