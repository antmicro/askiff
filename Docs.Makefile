# Make file for docs handling

SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = docs/src
BUILDDIR      = .build

.PHONY: help doctest clean html

help:
	uv run $(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)

doctest:
	uv run $(SPHINXBUILD) -b doctest "$(SOURCEDIR)" "$(BUILDDIR)/doctest"

clean:
	rm -rf "$(BUILDDIR)" "$(SOURCEDIR)/autoapi"
	
html:
	uv run $(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Catch-all target: route all unknown targets to Sphinx using the "make mode" option.
# $(O) is meant as a shortcut for $(SPHINXOPTS).
%:
	uv run $(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)