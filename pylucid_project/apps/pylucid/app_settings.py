# coding: utf-8
"""
    PyLucid App. settings
    ~~~~~~~~~~~~~~~~~~~~~
    
    settings witch only used in the PyLucid app.
"""

# Every Plugin output gets a html DIV or SPAN tag around.
# Here you can defined witch CSS class name the tag should used:
CSS_PLUGIN_CLASS_NAME = "PyLucidPlugins"

HEADFILE_INLINE_TEMPLATES = "pylucid/headfile_%s_inline.html"
HEADFILE_LINK_TEMPLATES = "pylucid/headfile_%s_link.html"
HEAD_FILES_URL_PREFIX = "headfile"

# File cache directory used for EditableHtmlHeadFile
# filesystem path is: MEDIA_ROOT + PYLUCID_MEDIA_DIR + CACHE_DIR
# URL if not cacheable in filesystem: /HEAD_FILES_URL_PREFIX/filepath
# URL if written into filesystem path: MEDIA_URL + PYLUCID_MEDIA_DIR + CACHE_DIR + filepath
CACHE_DIR = "headfile_cache" # store path: 

# i18n stuff:
I18N_DEBUG = False # Display many info around detecting current language

HTTP_GET_VIEW_NAME = "http_get_view"

# All PyLucid media files stored in a sub directory under the django media
# path. Used for building filesystem path and URLs.
# filesystem path: MEDIA_ROOT + PYLUCID_MEDIA_DIR
# URLs: MEDIA_URL + PYLUCID_MEDIA_DIR
PYLUCID_MEDIA_DIR = "PyLucid" # Without slashes at begin/end!