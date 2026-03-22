# MapSplat QGIS Plugin Makefile

PLUGINNAME = mapsplat

# QGIS plugin directory (adjust for your system)
QGISDIR ?= $(HOME)/.local/share/QGIS/QGIS3/profiles/default/python/plugins

PY_FILES = __init__.py mapsplat.py mapsplat_dockwidget.py exporter.py style_converter.py config_manager.py log_utils.py

EXTRAS = metadata.txt icon.png resources.qrc

RESOURCE_FILES = resources.py

HELP = help/build/html

.PHONY: default
default: compile

.PHONY: compile
compile: $(RESOURCE_FILES)

%.py : %.qrc
	pyrcc5 -o $@ $<

.PHONY: deploy
deploy: compile
	@echo "Deploying plugin to $(QGISDIR)/$(PLUGINNAME)"
	@mkdir -p $(QGISDIR)/$(PLUGINNAME)
	@mkdir -p $(QGISDIR)/$(PLUGINNAME)/templates
	@mkdir -p $(QGISDIR)/$(PLUGINNAME)/lib
	cp -f $(PY_FILES) $(QGISDIR)/$(PLUGINNAME)/
	cp -f $(EXTRAS) $(QGISDIR)/$(PLUGINNAME)/
	@if [ -f resources.py ]; then cp -f resources.py $(QGISDIR)/$(PLUGINNAME)/; fi
	@if [ -d templates ]; then cp -rf templates/* $(QGISDIR)/$(PLUGINNAME)/templates/ 2>/dev/null || true; fi
	@if [ -d lib ]; then cp -rf lib/* $(QGISDIR)/$(PLUGINNAME)/lib/ 2>/dev/null || true; fi
	@echo "Done!"

.PHONY: remove
remove:
	@echo "Removing plugin from $(QGISDIR)/$(PLUGINNAME)"
	rm -rf $(QGISDIR)/$(PLUGINNAME)

.PHONY: clean
clean:
	rm -f $(RESOURCE_FILES)
	rm -f *.pyc
	rm -rf __pycache__
	rm -rf .pytest_cache

.PHONY: test
test:
	python -m pytest test/ -v

.PHONY: package
package: compile
	@echo "Creating plugin package..."
	rm -f $(PLUGINNAME).zip
	mkdir -p $(PLUGINNAME)
	cp -f $(PY_FILES) $(PLUGINNAME)/
	cp -f $(EXTRAS) $(PLUGINNAME)/
	@if [ -f resources.py ]; then cp -f resources.py $(PLUGINNAME)/; fi
	@if [ -d templates ]; then cp -rf templates $(PLUGINNAME)/; fi
	@if [ -d lib ]; then cp -rf lib $(PLUGINNAME)/; fi
	@if [ -d docs ]; then cp -rf docs $(PLUGINNAME)/; fi
	zip -r $(PLUGINNAME).zip $(PLUGINNAME)
	rm -rf $(PLUGINNAME)
	@echo "Created $(PLUGINNAME).zip"

.PHONY: help
help:
	@echo "MapSplat Plugin Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  compile   - Compile resources (default)"
	@echo "  deploy    - Deploy plugin to QGIS plugins directory"
	@echo "  remove    - Remove plugin from QGIS plugins directory"
	@echo "  clean     - Remove compiled files"
	@echo "  test      - Run tests"
	@echo "  package   - Create plugin zip for distribution"
	@echo ""
	@echo "Variables:"
	@echo "  QGISDIR   - QGIS plugins directory (default: $(QGISDIR))"
