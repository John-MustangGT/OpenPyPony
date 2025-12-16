# OpenPonyLogger - CircuitPython Deployment Makefile
#
# Common tasks:
#   make deploy       - Deploy logger.py to Pico (auto-detect drive)
#   make clean-deploy - Clean install
#   make install-deps - Install CircuitPython libraries
#   make reset-pico   - Factory reset Pico filesystem
#   make check        - Check CIRCUITPY drive
#   make help         - Show this help

# Python interpreter
PYTHON := python3

# Deployment script
DEPLOY_SCRIPT := tools/deploy_to_pico.py

# Auto-detect CIRCUITPY drive
DRIVE ?= $(shell $(PYTHON) -c "import platform; \
	from pathlib import Path; \
	system = platform.system(); \
	paths = ['/Volumes/CIRCUITPY'] if system == 'Darwin' else \
	        ['/media/CIRCUITPY', '/media/$$USER/CIRCUITPY', '/run/media/$$USER/CIRCUITPY'] if system == 'Linux' else \
	        [f'{chr(d)}:/CIRCUITPY' for d in range(68, 91)]; \
	print(next((str(p) for p in [Path(x) for x in paths] if p.exists()), ''))")

# Colors for output
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_GREEN := \033[92m
COLOR_YELLOW := \033[93m
COLOR_CYAN := \033[96m
COLOR_RED := \033[91m

.PHONY: help
help:
	@echo ""
	@echo "$(COLOR_BOLD)OpenPonyLogger - CircuitPython Deployment$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_CYAN)Quick Commands:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make deploy$(COLOR_RESET)       - Deploy logger.py to Pico (auto-detect drive)"
	@echo "  $(COLOR_GREEN)make clean-deploy$(COLOR_RESET) - Clean install (removes old files)"
	@echo "  $(COLOR_GREEN)make install-deps$(COLOR_RESET) - Install CircuitPython libraries (requires circup)"
	@echo "  $(COLOR_GREEN)make reset-pico$(COLOR_RESET)   - Factory reset Pico filesystem (WARNING: DELETES ALL DATA)"
	@echo ""
	@echo "$(COLOR_CYAN)Development:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make check$(COLOR_RESET)        - Check if CIRCUITPY drive is mounted"
	@echo "  $(COLOR_GREEN)make backup$(COLOR_RESET)       - Backup current Pico files"
	@echo "  $(COLOR_GREEN)make serial$(COLOR_RESET)       - Connect to serial console"
	@echo "  $(COLOR_GREEN)make validate$(COLOR_RESET)     - Validate current deployment"
	@echo "  $(COLOR_GREEN)make diff$(COLOR_RESET)         - Show what would be deployed"
	@echo ""
	@echo "$(COLOR_CYAN)Manual:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make deploy DRIVE=/Volumes/CIRCUITPY$(COLOR_RESET)"
	@echo ""

.PHONY: check
check:
	@echo "Checking for CIRCUITPY drive..."
	@if [ -z "$(DRIVE)" ]; then \
		echo "$(COLOR_YELLOW)✗ CIRCUITPY drive not found$(COLOR_RESET)"; \
		echo "  Please mount your Pico and try again"; \
		exit 1; \
	else \
		echo "$(COLOR_GREEN)✓ Found: $(DRIVE)$(COLOR_RESET)"; \
		if [ -f "$(DRIVE)/boot_out.txt" ]; then \
			head -1 "$(DRIVE)/boot_out.txt"; \
		fi; \
	fi

.PHONY: deploy
deploy: check
	@echo "$(COLOR_BOLD)Deploying OpenPonyLogger to $(DRIVE)$(COLOR_RESET)"
	$(PYTHON) $(DEPLOY_SCRIPT) --drive $(DRIVE)

.PHONY: clean-deploy
clean-deploy: check
	@echo "$(COLOR_BOLD)Clean deployment to $(DRIVE)$(COLOR_RESET)"
	$(PYTHON) $(DEPLOY_SCRIPT) --drive $(DRIVE) --clean

.PHONY: install-deps
install-deps: check
	@echo "$(COLOR_BOLD)Installing CircuitPython libraries$(COLOR_RESET)"
	@if ! command -v circup &> /dev/null; then \
		echo "$(COLOR_RED)✗ circup not found!$(COLOR_RESET)"; \
		echo "  Install with: pip install circup"; \
		exit 1; \
	fi
	@echo "Installing libraries from circuitpython/requirements.txt..."
	@cd circuitpython && circup install -r requirements.txt --path $(DRIVE)
	@echo "$(COLOR_GREEN)✓ Libraries installed$(COLOR_RESET)"

.PHONY: reset-pico
reset-pico: check
	@echo "$(COLOR_RED)$(COLOR_BOLD)WARNING: This will ERASE ALL DATA on the Pico!$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)This includes:"
	@echo "  - All Python files (code.py, logger.py, etc.)"
	@echo "  - All libraries (/lib directory)"
	@echo "  - All settings (settings.toml, boot.py)"
	@echo "  - All user data$(COLOR_RESET)"
	@echo ""
	@read -p "Type 'RESET' to confirm: " confirm; \
	if [ "$$confirm" != "RESET" ]; then \
		echo "$(COLOR_YELLOW)Reset cancelled$(COLOR_RESET)"; \
		exit 1; \
	fi
	@echo ""
	@echo "Creating reset script..."
	@echo "import storage" > $(DRIVE)/code.py
	@echo "import os" >> $(DRIVE)/code.py
	@echo "print('Resetting filesystem...')" >> $(DRIVE)/code.py
	@echo "storage.erase_filesystem()" >> $(DRIVE)/code.py
	@echo "$(COLOR_GREEN)✓ Reset script deployed$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_YELLOW)Please eject and reset your Pico now.$(COLOR_RESET)"
	@echo "The Pico will:"
	@echo "  1. Boot and run the reset script"
	@echo "  2. Erase the filesystem"
	@echo "  3. Reboot with a clean filesystem"
	@echo ""
	@echo "After reset, run: make install-deps && make deploy"

.PHONY: backup
backup: check
	@echo "Backing up Pico files..."
	@mkdir -p backups
	@BACKUP_DIR="backups/backup_$$(date +%Y%m%d_%H%M%S)"; \
	mkdir -p "$$BACKUP_DIR"; \
	cp -r "$(DRIVE)"/* "$$BACKUP_DIR/" 2>/dev/null || true; \
	echo "$(COLOR_GREEN)✓ Backup saved to $$BACKUP_DIR$(COLOR_RESET)"

.PHONY: diff
diff: check
	@echo "$(COLOR_CYAN)Checking for differences...$(COLOR_RESET)"
	@echo ""
	@MODULES="code.py accelerometer.py config.py gps.py hardware_setup.py neopixel_handler.py oled.py rtc_handler.py sdcard.py serial_com.py utils.py"; \
	CHANGED=0; \
	MISSING=0; \
	IDENTICAL=0; \
	for f in $$MODULES; do \
		SRC="circuitpython/$$f"; \
		DST="$(DRIVE)/$$f"; \
		if [ ! -f "$$SRC" ]; then \
			continue; \
		fi; \
		if [ ! -f "$$DST" ]; then \
			echo "$(COLOR_GREEN)+ $$f (new file)$(COLOR_RESET)"; \
			MISSING=$$((MISSING + 1)); \
		elif ! cmp -s "$$SRC" "$$DST"; then \
			echo "$(COLOR_YELLOW)M $$f (modified)$(COLOR_RESET)"; \
			CHANGED=$$((CHANGED + 1)); \
		else \
			echo "$(COLOR_CYAN)= $$f (unchanged)$(COLOR_RESET)"; \
			IDENTICAL=$$((IDENTICAL + 1)); \
		fi; \
	done; \
	echo ""; \
	echo "Summary: $(COLOR_GREEN)$$MISSING new$(COLOR_RESET), $(COLOR_YELLOW)$$CHANGED modified$(COLOR_RESET), $(COLOR_CYAN)$$IDENTICAL unchanged$(COLOR_RESET)"; \
	if [ $$MISSING -eq 0 ] && [ $$CHANGED -eq 0 ]; then \
		echo "$(COLOR_GREEN)✓ Everything is up to date!$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_YELLOW)→ Run 'make deploy' to update$(COLOR_RESET)"; \
	fi

.PHONY: validate
validate: check
	@echo "Validating deployment..."
	@VALID=0; \
	REQUIRED="code.py hardware_setup.py utils.py"; \
	OPTIONAL="accelerometer.py config.py gps.py neopixel_handler.py oled.py rtc_handler.py sdcard.py serial_com.py"; \
	LIBS="lib/adafruit_lis3dh.mpy lib/adafruit_gps.mpy lib/adafruit_displayio_ssd1306.mpy lib/adafruit_display_text lib/adafruit_bitmap_font lib/neopixel.mpy"; \
	echo "$(COLOR_CYAN)Required modules:$(COLOR_RESET)"; \
	for f in $$REQUIRED; do \
		if [ -f "$(DRIVE)/$$f" ]; then \
			SIZE=$$(stat -f%z "$(DRIVE)/$$f" 2>/dev/null || stat -c%s "$(DRIVE)/$$f" 2>/dev/null); \
			echo "$(COLOR_GREEN)✓ $$f ($$SIZE bytes)$(COLOR_RESET)"; \
		else \
			echo "$(COLOR_RED)✗ Missing: $$f$(COLOR_RESET)"; \
			VALID=1; \
		fi; \
	done; \
	echo "$(COLOR_CYAN)Optional modules:$(COLOR_RESET)"; \
	for f in $$OPTIONAL; do \
		if [ -f "$(DRIVE)/$$f" ]; then \
			SIZE=$$(stat -f%z "$(DRIVE)/$$f" 2>/dev/null || stat -c%s "$(DRIVE)/$$f" 2>/dev/null); \
			echo "$(COLOR_GREEN)✓ $$f ($$SIZE bytes)$(COLOR_RESET)"; \
		else \
			echo "$(COLOR_YELLOW)○ Not found: $$f$(COLOR_RESET)"; \
		fi; \
	done; \
	echo "$(COLOR_CYAN)Libraries:$(COLOR_RESET)"; \
	for f in $$LIBS; do \
		if [ -f "$(DRIVE)/$$f" ]; then \
			SIZE=$$(stat -f%z "$(DRIVE)/$$f" 2>/dev/null || stat -c%s "$(DRIVE)/$$f" 2>/dev/null); \
			echo "$(COLOR_GREEN)✓ $$f ($$SIZE bytes)$(COLOR_RESET)"; \
		else \
			echo "$(COLOR_YELLOW)○ Not found: $$f$(COLOR_RESET)"; \
		fi; \
	done; \
	if [ $$VALID -eq 0 ]; then \
		echo "$(COLOR_GREEN)✓ All required modules present$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)✗ Missing required modules$(COLOR_RESET)"; \
	fi; \
	exit $$VALID

.PHONY: serial
serial:
	@echo "$(COLOR_CYAN)Connecting to serial console...$(COLOR_RESET)"
	@echo "Press Ctrl+A then K to exit"
	@sleep 1
	@# Try common serial port locations
	@if [ "$$(uname)" = "Darwin" ]; then \
		PORT=$$(ls /dev/tty.usbmodem* 2>/dev/null | head -1); \
		if [ -n "$$PORT" ]; then \
			screen "$$PORT" 115200; \
		else \
			echo "$(COLOR_YELLOW)No serial port found$(COLOR_RESET)"; \
		fi; \
	elif [ "$$(uname)" = "Linux" ]; then \
		PORT=$$(ls /dev/ttyACM* 2>/dev/null | head -1); \
		if [ -n "$$PORT" ]; then \
			screen "$$PORT" 115200; \
		else \
			echo "$(COLOR_YELLOW)No serial port found$(COLOR_RESET)"; \
		fi; \
	fi

.PHONY: watch
watch:
	@echo "$(COLOR_CYAN)Watching for file changes...$(COLOR_RESET)"
	@echo "Press Ctrl+C to stop"
	@while true; do \
		fswatch -1 circuitpython/*.py 2>/dev/null && make deploy; \
		inotifywait -e modify circuitpython/*.py 2>/dev/null && make deploy; \
		sleep 1; \
	done

.PHONY: clean
clean:
	@echo "Cleaning temporary files..."
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "$(COLOR_GREEN)✓ Cleaned$(COLOR_RESET)"

.PHONY: install-tools
install-tools:
	@echo "Installing deployment tools..."
	@echo ""
	@echo "$(COLOR_CYAN)Installing circup (CircuitPython library manager)$(COLOR_RESET)"
	pip install --upgrade circup
	@echo ""
	@echo "$(COLOR_GREEN)✓ Tools installed$(COLOR_RESET)"
	@echo ""
	@echo "Usage: make install-deps"

# Default target
.DEFAULT_GOAL := help
