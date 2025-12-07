# OpenPonyLogger - CircuitPython Deployment Makefile
#
# Common tasks:
#   make deploy       - Deploy to Pico (auto-detect drive)
#   make clean-deploy - Clean install
#   make web          - Just compress web assets
#   make install-deps - Install CircuitPython libraries
#   make check        - Check CIRCUITPY drive
#   make help         - Show this help

# Python interpreter
PYTHON := python3

# Deployment script
DEPLOY_SCRIPT := tools/deploy_to_pico.py

# Auto-detect CIRCUITPY drive
# Auto-detect CIRCUITPY drive
DRIVE ?= $(shell $(PYTHON) -c "import platform; \
	from pathlib import Path; \
	system = platform.system(); \
	paths = ['/Volumes/CIRCUITPY'] if system == 'Darwin' else \
	        ['/media/CIRCUITPY', '/media/$$USER/CIRCUITPY', '/run/media/$$USER/CIRCUITPY'] if system == 'Linux' else \
	        [f'{chr(d)}:/CIRCUITPY' for d in range(68, 91)]; \
	print(next((str(p) for p in paths if Path(p).exists()), ''))")

# Colors for output
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_GREEN := \033[92m
COLOR_YELLOW := \033[93m
COLOR_CYAN := \033[96m

SHELL := /bin/bash
PYTHON := venv/bin/python3
PIP := venv/bin/pip

.PHONY: venv
venv:
	@echo "Creating virtual environment..."
	python3 -m venv venv
	$(PIP) install --upgrade pip
	$(PIP) install circup mpy-cross pytest black
	@echo "✓ Virtual environment ready!"
	@echo "Activate with: source venv/bin/activate"

.PHONY: help
help:
	@echo ""
	@echo -e "$(COLOR_BOLD)OpenPonyLogger - CircuitPython Deployment$(COLOR_RESET)"
	@echo ""
	@echo -e "$(COLOR_CYAN)Quick Commands:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make deploy$(COLOR_RESET)       - Deploy to Pico (auto-detect drive)"
	@echo -e "  $(COLOR_GREEN)make deploy-mpy$(COLOR_RESET)   - Deploy with .mpy bytecode (faster!)"
	@echo -e "  $(COLOR_GREEN)make clean-deploy$(COLOR_RESET) - Clean install (removes old files)"
	@echo -e "  $(COLOR_GREEN)make web$(COLOR_RESET)          - Just compress and deploy web assets"
	@echo -e "  $(COLOR_GREEN)make install-deps$(COLOR_RESET) - Install CircuitPython libraries (requires circup)"
	@echo ""
	@echo -e "$(COLOR_CYAN)Development:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make check$(COLOR_RESET)        - Check if CIRCUITPY drive is mounted"
	@echo -e "  $(COLOR_GREEN)make backup$(COLOR_RESET)       - Backup current Pico files"
	@echo -e "  $(COLOR_GREEN)make serial$(COLOR_RESET)       - Connect to serial console"
	@echo -e "  $(COLOR_GREEN)make validate$(COLOR_RESET)     - Validate current deployment"
	@echo ""
	@echo -e "$(COLOR_CYAN)Compression:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make compress$(COLOR_RESET)     - Compress web assets to web_compressed/"
	@echo -e "  $(COLOR_GREEN)make stats$(COLOR_RESET)        - Show compression statistics"
	@echo ""
	@echo -e "$(COLOR_CYAN)Bytecode Compilation:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make install-mpy-cross$(COLOR_RESET) - Install mpy-cross compiler"
	@echo -e "  $(COLOR_GREEN)make compile-mpy$(COLOR_RESET)       - Compile .py to .mpy (test locally)"
	@echo ""
	@echo -e "$(COLOR_CYAN)Manual:$(COLOR_RESET)"
	@echo -e "  $(COLOR_GREEN)make deploy DRIVE=/Volumes/CIRCUITPY$(COLOR_RESET)"
	@echo ""

.PHONY: check
check:
	@echo "Checking for CIRCUITPY drive..."
	@if [ -z "$(DRIVE)" ]; then \
		echo -e "$(COLOR_YELLOW)✗ CIRCUITPY drive not found$(COLOR_RESET)"; \
		echo "  Please mount your Pico and try again"; \
		exit 1; \
	else \
		echo -e "$(COLOR_GREEN)✓ Found: $(DRIVE)$(COLOR_RESET)"; \
		if [ -f "$(DRIVE)/boot_out.txt" ]; then \
			head -1 "$(DRIVE)/boot_out.txt"; \
		fi; \
	fi

.PHONY: deploy
deploy: check
	@echo -e "$(COLOR_BOLD)Deploying OpenPonyLogger to $(DRIVE)$(COLOR_RESET)"
	$(PYTHON) $(DEPLOY_SCRIPT) --drive $(DRIVE)

.PHONY: deploy-mpy
deploy-mpy: check
	@echo -e "$(COLOR_BOLD)Deploying with .mpy bytecode to $(DRIVE)$(COLOR_RESET)"
	$(PYTHON) $(DEPLOY_SCRIPT) --drive $(DRIVE) --mpy
	@echo ""
	@echo -e "$(COLOR_CYAN)Cleaning old .py files...$(COLOR_RESET)"
	@rm -f "$(DRIVE)/code.py" 2>/dev/null || true
	@rm -f "$(DRIVE)/accel_test.py" 2>/dev/null || true
	@echo -e "$(COLOR_GREEN)✓ Deployment complete!$(COLOR_RESET)"

.PHONY: clean-deploy
clean-deploy: check
	@echo -e "$(COLOR_BOLD)Clean deployment to $(DRIVE)$(COLOR_RESET)"
	$(PYTHON) $(DEPLOY_SCRIPT) --drive $(DRIVE) --clean

.PHONY: install-mpy-cross
install-mpy-cross:
	@echo "Installing mpy-cross..."
	pip install mpy-cross
	@echo -e "$(COLOR_GREEN)✓ mpy-cross installed$(COLOR_RESET)"
	@echo ""
	@echo "Usage: make deploy-mpy"

.PHONY: compile-mpy
compile-mpy:
	@echo "Compiling Python files to .mpy..."
	@mkdir -p build/mpy
	@for f in *.py; do \
		if [ -f "$$f" ]; then \
			echo "  Compiling $$f..."; \
			mpy-cross "$$f" -o "build/mpy/$${f%.py}.mpy" 2>/dev/null || \
				echo -e "$(COLOR_WARNING)  Failed to compile $$f$(COLOR_RESET)"; \
		fi; \
	done
	@echo ""
	@echo -e "$(COLOR_GREEN)✓ Compiled to build/mpy/$(COLOR_RESET)"
	@ls -lh build/mpy/*.mpy 2>/dev/null || true

.PHONY: web
web: check
	@echo -e "$(COLOR_BOLD)Deploying web assets only$(COLOR_RESET)"
	$(PYTHON) $(DEPLOY_SCRIPT) --drive $(DRIVE)

.PHONY: install-deps
install-deps: check
	@echo -e "$(COLOR_BOLD)Installing CircuitPython libraries$(COLOR_RESET)"
	$(PYTHON) $(DEPLOY_SCRIPT) --drive $(DRIVE) --install-deps

.PHONY: compress
compress:
	@echo "Compressing web assets..."
	@mkdir -p web_compressed
	$(PYTHON) tools/prepare_web_assets_cp.py web/ web_compressed/

.PHONY: stats
stats: compress
	@echo ""
	@echo -e "$(COLOR_CYAN)Compression Statistics:$(COLOR_RESET)"
	@echo ""
	@ls -lh web_compressed/*.gz | awk '{printf "  %s: %s\n", $$9, $$5}'
	@echo ""

.PHONY: backup
backup: check
	@echo "Backing up Pico files..."
	@mkdir -p backups
	@BACKUP_DIR="backups/backup_$$(date +%Y%m%d_%H%M%S)"; \
	mkdir -p "$$BACKUP_DIR"; \
	cp -r "$(DRIVE)"/* "$$BACKUP_DIR/"; \
	echo -e "$(COLOR_GREEN)✓ Backup saved to $$BACKUP_DIR$(COLOR_RESET)"

.PHONY: validate
validate: check
	@echo "Validating deployment..."
	@VALID=0; \
	FILES="code.py web_server_gz.py web/asset_map.py web/index.html.gz"; \
	for f in $$FILES; do \
		if [ -f "$(DRIVE)/$$f" ]; then \
			SIZE=$$(stat -f%z "$(DRIVE)/$$f" 2>/dev/null || stat -c%s "$(DRIVE)/$$f" 2>/dev/null); \
			echo -e "$(COLOR_GREEN)✓ $$f ($$SIZE bytes)$(COLOR_RESET)"; \
		else \
			echo -e "$(COLOR_YELLOW)✗ Missing: $$f$(COLOR_RESET)"; \
			VALID=1; \
		fi; \
	done; \
	exit $$VALID

.PHONY: serial
serial:
	@echo -e "$(COLOR_CYAN)Connecting to serial console...$(COLOR_RESET)"
	@echo "Press Ctrl+A then K to exit"
	@sleep 1
	@# Try common serial port locations
	@if [ "$$(uname)" = "Darwin" ]; then \
		PORT=$$(ls /dev/tty.usbmodem* 2>/dev/null | head -1); \
		if [ -n "$$PORT" ]; then \
			screen "$$PORT" 115200; \
		else \
		  	echo -e "$(COLOR_YELLOW)No serial port found$(COLOR_RESET)"; \
		fi; \
	elif [ "$$(uname)" = "Linux" ]; then \
		PORT=$$(ls /dev/ttyACM* 2>/dev/null | head -1); \
		if [ -n "$$PORT" ]; then \
			screen "$$PORT" 115200; \
		else \
			echo -e "$(COLOR_YELLOW)No serial port found$(COLOR_RESET)"; \
		fi; \
	fi

.PHONY: watch
watch:
	@echo -e "$(COLOR_CYAN)Watching for file changes...$(COLOR_RESET)"
	@echo "Press Ctrl+C to stop"
	@while true; do \
		fswatch -1 code.py web_server_gz.py web/*.html web/*.css web/*.js 2>/dev/null && make deploy; \
		inotifywait -e modify code.py web_server_gz.py web/*.html web/*.css web/*.js 2>/dev/null && make deploy; \
		sleep 1; \
	done

.PHONY: clean
clean:
	@echo "Cleaning temporary files..."
	@rm -rf web_compressed/
	@rm -f *.pyc __pycache__
	@echo -e "$(COLOR_GREEN)✓ Cleaned$(COLOR_RESET)"

.PHONY: install-tools
install-tools:
	@echo "Installing deployment tools..."
	@echo ""
	@echo -e "$(COLOR_CYAN)Installing circup (CircuitPython library manager)$(COLOR_RESET)"
	pip install --upgrade circup
	@echo ""
	@echo -e "$(COLOR_GREEN)✓ Tools installed$(COLOR_RESET)"
	@echo ""
	@echo "Usage: make install-deps"

# Default target
.DEFAULT_GOAL := help
