import doctest
from datetime import datetime

from antmicro_sphinx_utils.defaults import antmicro_html, antmicro_latex
from antmicro_sphinx_utils.defaults import extensions as default_extensions
from antmicro_sphinx_utils.defaults import myst_enable_extensions as default_myst_enable_extensions
from antmicro_sphinx_utils.defaults import myst_fence_as_directive as default_myst_fence_as_directive

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# sys.path.insert(0, os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

# General information about the project.
project = "A SKiff documentation"
basic_filename = "askiff-docs--doctype"
authors = "Antmicro"
copyright = f"{authors}, {datetime.now().year}"  # noqa: A001

# The short X.Y version.
version = ""
# The full version, including alpha/beta/rc tags.
release = ""

# This is temporary before the clash between myst-parser and immaterial is fixed
sphinx_immaterial_override_builtin_admonitions = False

numfig = True

# If you need to add extensions just add to those lists
extensions = default_extensions
myst_enable_extensions = default_myst_enable_extensions
myst_fence_as_directive = default_myst_fence_as_directive

myst_substitutions = {"project": project}

myst_heading_anchors = 4

today_fmt = "%Y-%m-%d"

todo_include_todos = False

# -- Options for HTML output ---------------------------------------------------

html_theme = "sphinx_immaterial"

html_last_updated_fmt = today_fmt

html_show_sphinx = False

(html_logo, html_theme_options, html_context) = antmicro_html()

html_title = project

(latex_elements, latex_documents, latex_logo, latex_additional_files) = antmicro_latex(basic_filename, authors, project)

extensions.extend(
    [
        "sphinx.ext.autodoc",
        # "sphinx.ext.autosummary",
        "sphinx_immaterial.apidoc",
        "sphinx.ext.napoleon",
        "sphinx.ext.doctest",
        "sphinx.ext.intersphinx",
        # "sphinx_autodoc_typehints",
    ]
)


# --- Autodoc ---
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "private-members": False,
}
# autosummary_imported_members = True
# autosummary_generate = True

# --- Type hints ---
autodoc_typehints = "both"
autodoc_typehints_format = "short"
autodoc_preserve_defaults = True

apidoc_modules = {
    "askiff": "../../askiff",  # path to your package
}


# Avoid duplication with Google docstrings
napoleon_use_rtype = False

doctest_default_flags = doctest.ELLIPSIS

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}  # type: ignore
