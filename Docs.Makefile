# Make file for docs handling

SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = docs/src
BUILDDIR      = .build
ABSBUILDDIR   = $(abspath $(BUILDDIR))

.PHONY: help doctest clean html

help:
	uv run $(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(ABSBUILDDIR)" $(SPHINXOPTS)

doctest:
	uv run $(SPHINXBUILD) -b doctest "$(SOURCEDIR)" "$(ABSBUILDDIR)/doctest"

clean:
	rm -rf "$(ABSBUILDDIR)" "$(SOURCEDIR)/autoapi"
	
html:
	uv run $(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(ABSBUILDDIR)" $(SPHINXOPTS) $(O)

# Catch-all target: route all unknown targets to Sphinx using the "make mode" option.
# $(O) is meant as a shortcut for $(SPHINXOPTS).
%:
	uv run $(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(ABSBUILDDIR)" $(SPHINXOPTS) $(O)