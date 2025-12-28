# OpenPonyLogger - Deployment Makefile (TOML-based)
#
# Uses deploy.toml for configuration
#
# Common tasks:
#   make deploy       - Deploy using deploy.toml settings
#   make deploy-mpy   - Deploy with .mpy compilation
#   make clean-deploy - Deploy and clean orphaned files
#   make backup       - Create backup only
#   make validate     - Validate current deployment
#   make help         - Show this help

# Python interpreter
PYTHON := python3

# Deployment script
DEPLOY_SCRIPT := deploy_to_pico.py

# Configuration file
DEPLOY_CONFIG := deploy.toml

# Colors for output
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_GREEN := \033[92m
COLOR_YELLOW := \033[93m
COLOR_CYAN := \033[96m

.PHONY: help
help:
	@echo ""
	@echo "$(COLOR_BOLD)OpenPonyLogger - TOML-Based Deployment$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_CYAN)Quick Commands:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make deploy$(COLOR_RESET)       - Deploy using deploy.toml settings"
	@echo "  $(COLOR_GREEN)make deploy-mpy$(COLOR_RESET)   - Deploy with .mpy bytecode compilation"
	@echo "  $(COLOR_GREEN)make clean-deploy$(COLOR_RESET) - Deploy and delete orphaned files"
	@echo "  $(COLOR_GREEN)make validate$(COLOR_RESET)     - Validate deployment (check files)"
	@echo ""
	@echo "$(COLOR_CYAN)Configuration:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make edit-config$(COLOR_RESET)  - Edit deploy.toml"
	@echo "  $(COLOR_GREEN)make show-config$(COLOR_RESET)  - Show current configuration"
	@echo ""
	@echo "$(COLOR_CYAN)Backup & Restore:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make backup$(COLOR_RESET)       - Create backup of Pico contents"
	@echo "  $(COLOR_GREEN)make list-backups$(COLOR_RESET) - List available backups"
	@echo ""
	@echo "$(COLOR_CYAN)Development:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make check$(COLOR_RESET)        - Check if CIRCUITPY drive is mounted"
	@echo "  $(COLOR_GREEN)make serial$(COLOR_RESET)       - Connect to serial console"
	@echo "  $(COLOR_GREEN)make install-deps$(COLOR_RESET) - Install CircuitPython libraries (circup)"
	@echo ""
	@echo "$(COLOR_CYAN)Manual Override:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make deploy DRIVE=/Volumes/CIRCUITPY$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make deploy CONFIG=custom.toml$(COLOR_RESET)"
	@echo ""

.PHONY: deploy
deploy:
	@echo "$(COLOR_BOLD)Deploying with deploy.toml configuration$(COLOR_RESET)"
	@$(PYTHON) $(DEPLOY_SCRIPT) $(if $(CONFIG),--config $(CONFIG)) $(if $(DRIVE),--drive $(DRIVE))

.PHONY: deploy-mpy
deploy-mpy:
	@echo "$(COLOR_BOLD)Deploying with .mpy compilation$(COLOR_RESET)"
	@$(PYTHON) $(DEPLOY_SCRIPT) --mpy $(if $(CONFIG),--config $(CONFIG)) $(if $(DRIVE),--drive $(DRIVE))

.PHONY: clean-deploy
clean-deploy:
	@echo "$(COLOR_BOLD)Deploying and cleaning orphaned files$(COLOR_RESET)"
	@$(PYTHON) $(DEPLOY_SCRIPT) --clean $(if $(CONFIG),--config $(CONFIG)) $(if $(DRIVE),--drive $(DRIVE))

.PHONY: validate
validate:
	@echo "$(COLOR_CYAN)Validating deployment...$(COLOR_RESET)"
	@$(PYTHON) -c "from $(DEPLOY_SCRIPT:.py=) import *; \
		config = DeploymentConfig('$(DEPLOY_CONFIG)'); \
		deployer = Deployer(config); \
		deployer.validate_deployment()"

.PHONY: backup
backup:
	@echo "$(COLOR_CYAN)Creating backup...$(COLOR_RESET)"
	@$(PYTHON) -c "from $(DEPLOY_SCRIPT:.py=) import *; \
		config = DeploymentConfig('$(DEPLOY_CONFIG)'); \
		deployer = Deployer(config); \
		deployer.create_backup()"

.PHONY: list-backups
list-backups:
	@echo "$(COLOR_CYAN)Available backups:$(COLOR_RESET)"
	@ls -lh backups/ 2>/dev/null || echo "No backups found"

.PHONY: check
check:
	@echo "$(COLOR_CYAN)Checking for CIRCUITPY drive...$(COLOR_RESET)"
	@$(PYTHON) -c "from $(DEPLOY_SCRIPT:.py=) import *; \
		config = DeploymentConfig('$(DEPLOY_CONFIG)'); \
		try: \
			deployer = Deployer(config); \
			print('$(COLOR_GREEN)✓ Found:', deployer.drive.path, '$(COLOR_RESET)'); \
			print('  Free space:', deployer.drive.get_free_space(), 'bytes'); \
		except SystemExit: \
			pass"

.PHONY: edit-config
edit-config:
	@$${EDITOR:-nano} $(DEPLOY_CONFIG)

.PHONY: show-config
show-config:
	@echo "$(COLOR_CYAN)Current deployment configuration:$(COLOR_RESET)"
	@cat $(DEPLOY_CONFIG)

.PHONY: install-deps
install-deps:
	@echo "$(COLOR_CYAN)Installing CircuitPython libraries with circup...$(COLOR_RESET)"
	@if command -v circup >/dev/null 2>&1; then \
		$(PYTHON) -c "from $(DEPLOY_SCRIPT:.py=) import *; \
			config = DeploymentConfig('$(DEPLOY_CONFIG)'); \
			deployer = Deployer(config); \
			libs = config.get('circup.requirements', []); \
			import subprocess; \
			for lib in libs: \
				print(f'Installing {lib}...'); \
				subprocess.run(['circup', 'install', '--path', str(deployer.drive.path), lib])"; \
	else \
		echo "$(COLOR_YELLOW)circup not installed$(COLOR_RESET)"; \
		echo "Install with: pip install circup"; \
	fi

.PHONY: serial
serial:
	@echo "$(COLOR_CYAN)Connecting to serial console...$(COLOR_RESET)"
	@echo "Press Ctrl+A then K to exit"
	@sleep 1
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

.PHONY: install-tools
install-tools:
	@echo "$(COLOR_CYAN)Installing deployment tools...$(COLOR_RESET)"
	@pip install toml circup mpy-cross
	@echo "$(COLOR_GREEN)✓ Tools installed$(COLOR_RESET)"

.PHONY: clean
clean:
	@echo "$(COLOR_CYAN)Cleaning temporary files...$(COLOR_RESET)"
	@rm -rf web_compressed/
	@rm -f *.pyc
	@rm -rf __pycache__
	@echo "$(COLOR_GREEN)✓ Cleaned$(COLOR_RESET)"

# Default target
.DEFAULT_GOAL := help
