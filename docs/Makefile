SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = src
BUILDDIR      = .build

.PHONY: help doctest clean

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)

doctest:
	$(SPHINXBUILD) -b doctest "$(SOURCEDIR)" "$(BUILDDIR)/doctest"

clean:
	rm -rf "$(BUILDDIR)"

# Catch-all target: route all unknown targets to Sphinx using the "make mode" option.
# $(O) is meant as a shortcut for $(SPHINXOPTS).
%:
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)