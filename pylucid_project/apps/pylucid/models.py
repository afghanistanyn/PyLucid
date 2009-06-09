# coding: utf-8

"""
    PyLucid.models.Page
    ~~~~~~~~~~~~~~~~~~~

    New PyLucid models since v0.9

    TODO:
        Where to store bools like: showlinks, permitViewPublic ?

    Last commit info:
    ~~~~~~~~~~~~~~~~~
    $LastChangedDate: $
    $Rev: $
    $Author: $

    :copyleft: 2009 by the PyLucid team, see AUTHORS for more details.
    :license: GNU GPL v3 or above, see LICENSE for more details.
"""

import os
import warnings
import posixpath
import mimetypes
from xml.sax.saxutils import escape

from django.db import models
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site
from django.utils.translation import ugettext as _
from django.contrib.auth.models import User, Group
from django.template.loader import render_to_string
from django.contrib.sites.managers import CurrentSiteManager

from pylucid.system.auto_model_info import UpdateInfoBaseModel, UpdateInfoBaseModelManager
from pylucid.system import headfile


class PageTreeManager(UpdateInfoBaseModelManager):
    """
    Manager class for PageTree model
    
    inherited from UpdateInfoBaseModelManager:
        get_or_create() method, witch expected a request object as the first argument.
    """
    def get_root_page(self):
        """ returns the 'first' page tree entry for a '/'-root url """
        queryset = PageTree.on_site.all().filter(parent=None).order_by("position")
        try:
            root_page = queryset[0]
        except IndexError, err:
            if PageTree.on_site.count() == 0:
                raise IndexError("There exist no PageTree items! Have you install PyLucid?")
            else:
                raise
        return root_page
    
    def get_model_instance(self, request, ModelClass, pagetree=None):
        """
        Shared function for getting a model instance from the given model witch has
        a foreignkey to PageTree and Language model.
        Use the current language or the system default language.
        If pagetree==None: Use request.PYLUCID.pagetree
        """
        # client favored Language instance:
        lang_entry = request.PYLUCID.lang_entry
        # default Language instance set in system preferences:
        default_lang_entry = request.PYLUCID.default_lang_entry
        
        lang_entry = request.PYLUCID.lang_entry
        default_lang_entry = request.PYLUCID.default_lang_entry
        
        if not pagetree:
            # current pagetree instance
            pagetree = request.PYLUCID.pagetree
            
        queryset = ModelClass.objects.all().filter(page=pagetree)
        try:
            # Try to get the current used language
            return queryset.get(lang=lang_entry)
        except ModelClass.DoesNotExist:
            # Get the PageContent entry in the system default language
            return queryset.get(lang=default_lang_entry)
    
    def get_pagemeta(self, request, pagetree=None):
        """
        Returns the PageMeta instance for pagetree and language.
        If there is no PageMeta in the current language, use the system default language.
        If pagetree==None: Use request.PYLUCID.pagetree
        """
        return self.get_model_instance(request, PageMeta, pagetree)
    
    def get_pagecontent(self, request, pagetree=None):
        """
        Returns the PageContent instance for pagetree and language.
        If there is no PageContent in the current language, use the system default language.
        If pagetree==None: Use request.PYLUCID.pagetree
        """
        return self.get_model_instance(request, PageContent, pagetree)
    
    def get_page_from_url(self, url_path):
        """ returns a tuple the page tree instance from the given url_path"""
        path = url_path.split("/")
        site = Site.objects.get_current()
        page = None
        for no, page_slug in enumerate(path):
            try:
                page = PageTree.objects.get(site=site, parent=page, slug=page_slug)
            except PageTree.DoesNotExist:
                raise PageTree.DoesNotExist("Wrong url part: %s" % escape(page_slug))

            if page.type == PageTree.PLUGIN_TYPE:
                # It's a plugin
                prefix_url = "/".join(path[:no+1])
                rest_url = "/".join(path[no+1:])
#                if not rest_url.endswith("/"):
#                    rest_url += "/"
                return (page, prefix_url, rest_url)

        return (page, None, None)

    def get_backlist(self, request, pagetree=None):
        """
        Generate a list of backlinks, usefull for generating a "You are here" breadcrumb navigation.
        TODO: filter showlinks and permit settings
        TODO: filter current site
        FIXME: Think this created many database requests
        """
        if pagetree == None:
            pagetree = request.PYLUCID.pagetree
        
        pagemeta = self.get_pagemeta(request, pagetree)
        url = pagemeta.get_absolute_url()
        title = pagemeta.title_or_slug()
        
        backlist = [{"url": url, "title": title}]
        
        parent = pagetree.parent
        if parent: 
            # insert parent links
            backlist = self.get_backlist(request, parent) + backlist

        return backlist



class PageTree(UpdateInfoBaseModel):
    """
    The CMS page tree
    
    inherited attributes from UpdateInfoBaseModel:
        createtime     -> datetime of creation
        lastupdatetime -> datetime of the last change
        createby       -> ForeignKey to user who creaded this entry
        lastupdateby   -> ForeignKey to user who has edited this entry
    """
    PAGE_TYPE = 'C'
    PLUGIN_TYPE = 'P'

    TYPE_CHOICES = (
        (PAGE_TYPE, 'CMS-Page'),
        (PLUGIN_TYPE , 'PluginPage'),
    )
    TYPE_DICT = dict(TYPE_CHOICES)

    objects = PageTreeManager()

    id = models.AutoField(primary_key=True)

    site = models.ForeignKey(Site)
    on_site = CurrentSiteManager()

    parent = models.ForeignKey("self", null=True, blank=True, help_text="the higher-ranking father page")
    position = models.SmallIntegerField(default=0,
        help_text="ordering weight for sorting the pages in the menu.")
    slug = models.SlugField(unique=False, help_text="(for building URLs)")
    description = models.CharField(blank=True, max_length=150, help_text="For internal use")

    type = models.CharField(max_length=1, choices=TYPE_CHOICES)

    design = models.ForeignKey("Design", help_text="Page Template, CSS/JS files")

    showlinks = models.BooleanField(default=True,
        help_text="Put the Link to this page into Menu/Sitemap etc.?"
    )
    permitViewGroup = models.ForeignKey(Group, related_name="%(class)s_permitViewGroup",
        help_text="Limit viewable to a group?",
        null=True, blank=True, 
    )
    permitEditGroup = models.ForeignKey(Group, related_name="%(class)s_permitEditGroup",
        help_text="Usergroup how can edit this page.",
        null=True, blank=True,
    )

    def get_absolute_url(self):
        """ absolute url *without* language code (without domain/host part) """
        if self.parent:
            parent_shortcut = self.parent.get_absolute_url()
            return parent_shortcut + self.slug + "/"
        else:
            return "/" + self.slug + "/"

    def __unicode__(self):
        return u"PageTree '%s' (site: %s, type: %s)" % (self.slug, self.site.name, self.TYPE_DICT[self.type])

    class Meta:
        unique_together=(("site", "slug", "parent"),)
        
        # FIXME: It would be great if we can order by get_absolute_url()
        ordering = ("site", "id", "position")


#------------------------------------------------------------------------------


class Language(models.Model):
    code = models.CharField(unique=True, max_length=5)
    description = models.CharField(max_length=150, help_text="Description of the Language")

    permitViewGroup = models.ForeignKey(Group, related_name="%(class)s_permitViewGroup",
        help_text="Limit viewable to a group for a complete language section?",
        null=True, blank=True, 
    )

    def __unicode__(self):
        return u"Language %s - %s" % (self.code, self.description)

    class Meta:
        ordering = ("code",)


#------------------------------------------------------------------------------

class i18nPageTreeBaseModel(models.Model):
    """
    Base model for PageMeta, PluginPage and PageContent
    """
    page = models.ForeignKey(PageTree)
    lang = models.ForeignKey(Language)
    
    def get_absolute_url(self):
        """ absolute url *with* language code (without domain/host part) """
        lang_code = self.lang.code
        page_url = self.page.get_absolute_url()
        return "/" + lang_code + page_url
    
    def get_site(self):
        return self.page.site
    
    class Meta:
        abstract = True



class PageMeta(i18nPageTreeBaseModel, UpdateInfoBaseModel):
    """
    Meta data for PageContent or PluginPage
    
    inherited attributes from i18nPageTreeBaseModel:
        page -> ForeignKey to PageTree
        lang -> ForeignKey to Language
        get_absolute_url()
    
    inherited attributes from UpdateInfoBaseModel:
        createtime     -> datetime of creation
        lastupdatetime -> datetime of the last change
        createby       -> ForeignKey to user who creaded this entry
        lastupdateby   -> ForeignKey to user who has edited this entry
    """
    name = models.CharField(blank=True, max_length=150,
        help_text="Sort page name (for link text in e.g. menu)"
    )
    title = models.CharField(blank=True, max_length=256,
        help_text="A long page title (for e.g. page title or link title text)"
    )
    keywords = models.CharField(blank=True, max_length=255,
        help_text="Keywords for the html header. (separated by commas)"
    )
    description = models.CharField(blank=True, max_length=255, help_text="For html header")

    permitViewGroup = models.ForeignKey(Group, related_name="%(class)s_permitViewGroup",
        help_text="Limit viewable to a group?",
        null=True, blank=True, 
    )

    def title_or_slug(self):
        """ The page title is optional, if not exist, used the slug from the page tree """
        return self.title or self.page.slug

    def __unicode__(self):
        return u"PageMeta for page: '%s' (lang: '%s')" % (self.page.slug, self.lang.code)
    
    class Meta:
        unique_together = (("page","lang"),)
        ordering = ("page", "lang")

#------------------------------------------------------------------------------


class PluginPage(i18nPageTreeBaseModel, UpdateInfoBaseModel):
    """
    A plugin page
    
    inherited attributes from i18nPageTreeBaseModel:
        page -> ForeignKey to PageTree
        lang -> ForeignKey to Language
        get_absolute_url()
    
    inherited attributes from UpdateInfoBaseModel:
        createtime     -> datetime of creation
        lastupdatetime -> datetime of the last change
        createby       -> ForeignKey to user who creaded this entry
        lastupdateby   -> ForeignKey to user who has edited this entry
    """
    APP_LABEL_CHOICES = [(app,app) for app in settings.INSTALLED_APPS]
    
    pagemeta = models.ForeignKey(PageMeta)
    
    app_label = models.CharField(max_length=256, choices=APP_LABEL_CHOICES,
        help_text="The app lable witch is in settings.INSTALLED_APPS"
    )
    
    def title_or_slug(self):
        """ The page title is optional, if not exist, used the slug from the page tree """
        return self.pagemeta.title or self.page.slug
    
    def get_plugin_name(self):
        return self.app_label.split(".")[-1]
    
    def save(self, *args, **kwargs):
        if not self.page.type == self.page.PLUGIN_TYPE:
            # FIXME: Better error with django model validation?
            raise AssertionError("Plugin can only exist on a plugin type tree entry!")
        return super(PluginPage, self).save(*args, **kwargs)
    
    def __unicode__(self):
        return u"PluginPage '%s' (page: %s)" % (self.app_label, self.page)
    
    class Meta:
        unique_together = (("page","lang"),)
        ordering = ("page", "lang")


#------------------------------------------------------------------------------


class PageContentManager(UpdateInfoBaseModelManager):
    """
    Manager class for PageContent model
    
    inherited from UpdateInfoBaseModelManager:
        get_or_create() method, witch expected a request object as the first argument.
    """    
    def get_sub_pages(self, pagecontent):
        """
        returns a list of all sub pages for the given PageContent instance
        TODO: filter showlinks and permit settings
        TODO: filter current site
        """
        current_lang = pagecontent.lang
        current_page = pagecontent.page
        sub_pages = PageContent.objects.all().filter(page__parent=current_page, lang=current_lang)
        return sub_pages   


class PageContent(i18nPageTreeBaseModel, UpdateInfoBaseModel):
    """
    A normal CMS Page with text content.

    inherited attributes from i18nPageTreeBaseModel:
        page -> ForeignKey to PageTree
        lang -> ForeignKey to Language
        get_absolute_url()

    inherited attributes from UpdateInfoBaseModel:
        createtime     -> datetime of creation
        lastupdatetime -> datetime of the last change
        createby       -> ForeignKey to user who creaded this entry
        lastupdateby   -> ForeignKey to user who has edited this entry
    """
    # IDs used in other parts of PyLucid, too
    MARKUP_CREOLE       = 6
    MARKUP_HTML         = 0
    MARKUP_HTML_EDITOR  = 1
    MARKUP_TINYTEXTILE  = 2
    MARKUP_TEXTILE      = 3
    MARKUP_MARKDOWN     = 4
    MARKUP_REST         = 5

    MARKUP_CHOICES = (
        (MARKUP_CREOLE      , u'Creole wiki markup'),
        (MARKUP_HTML        , u'html'),
        (MARKUP_HTML_EDITOR , u'html + JS-Editor'),
        (MARKUP_TINYTEXTILE , u'textile'),
        (MARKUP_TEXTILE     , u'Textile (original)'),
        (MARKUP_MARKDOWN    , u'Markdown'),
        (MARKUP_REST        , u'ReStructuredText'),
    )
    MARKUP_DICT = dict(MARKUP_CHOICES)
    #--------------------------------------------------------------------------
    
    objects = PageContentManager()

    pagemeta = models.ForeignKey(PageMeta)

    content = models.TextField(blank=True, help_text="The CMS page content.")
    markup = models.IntegerField(db_column="markup_id", max_length=1, choices=MARKUP_CHOICES)

    def title_or_slug(self):
        """ The page title is optional, if not exist, used the slug from the page tree """
        return self.pagemeta.title or self.page.slug

    def save(self, *args, **kwargs):
        if not self.page.type == self.page.PAGE_TYPE:
            # FIXME: Better error with django model validation?
            raise AssertionError("PageContent can only exist on a page type tree entry!")
        return super(PageContent, self).save(*args, **kwargs)

    def __unicode__(self):
        return u"PageContent '%s' (%s)" % (self.page.slug, self.lang)

    class Meta:
        unique_together = (("page","lang"),)
        ordering = ("page", "lang")


#------------------------------------------------------------------------------

class Design(UpdateInfoBaseModel):
    """
    Page design: template + CSS/JS files
    
    inherited attributes from UpdateInfoBaseModel:
        createtime     -> datetime of creation
        lastupdatetime -> datetime of the last change
        createby       -> ForeignKey to user who creaded this entry
        lastupdateby   -> ForeignKey to user who has edited this entry
    """
    site = models.ManyToManyField(Site, default=[settings.SITE_ID])
    on_site = CurrentSiteManager()
    
    name = models.CharField(unique=True, max_length=150, help_text="Name of this design combination",)
    template = models.CharField(max_length=128, help_text="filename of the used template for this page")
    headfiles = models.ManyToManyField("EditableHtmlHeadFile", null=True, blank=True,
        help_text="Static files (stylesheet/javascript) for this page, included in html head via link tag"
    )

    def save(self, *args, **kwargs):
        assert isinstance(self.template, basestring), \
            "Template must be name as a String, not a template instance!"

        return super(Design, self).save(*args, **kwargs)

    def __unicode__(self):
        return u"Page design '%s'" % self.name
    
    class Meta:
        ordering = ("template",)


#------------------------------------------------------------------------------

class EditableHtmlHeadFileManager(UpdateInfoBaseModelManager):
    def get_HeadfileLink(self, filename):
        """
        returns a pylucid.system.headfile.Headfile instance
        """
        db_instance = self.get(filename=filename)
        return headfile.HeadfileLink(filename=db_instance.filename)#, content=db_instance.content)
        

class EditableHtmlHeadFile(UpdateInfoBaseModel):
    """
    Storage for editable static text files, e.g.: stylesheet / javascript.
    
    inherited attributes from UpdateInfoBaseModel:
        createtime     -> datetime of creation
        lastupdatetime -> datetime of the last change
        createby       -> ForeignKey to user who creaded this entry
        lastupdateby   -> ForeignKey to user who has edited this entry
    """
    objects = EditableHtmlHeadFileManager()
    
    site = models.ManyToManyField(Site, default=[settings.SITE_ID])
    on_site = CurrentSiteManager()
    
    filepath = models.CharField(max_length=256)
    mimetype = models.CharField(max_length=64)
    html_attributes = models.CharField(max_length=256, null=False, blank=True,
        help_text='Additional html tag attributes (CSS example: media="screen")'
    )
    description = models.TextField(null=True, blank=True)
    content = models.TextField()
    
    def get_cachepath(self):
        """
        filesystem path with filename.
        TODO: Install section sould create the directories!
        """
        return os.path.join(
            settings.MEDIA_ROOT, settings.PYLUCID.PYLUCID_MEDIA_DIR, settings.PYLUCID.CACHE_DIR,
            self.filepath
        )
        
    def save_cache_file(self):
        """ Try to cache the head file into filesystem (Only worked, if python process has write rights) """
        cachepath = self.get_cachepath()
        try:
            f = file(cachepath, "w")
            f.write(self.content)
            f.close()
        except Exception, err:
            warnings.warn("Can't cache EditableHtmlHeadFile into %r: %s" % (cachepath, err))
        else:
            if settings.DEBUG:
                warnings.warn("EditableHtmlHeadFile cached successful into: %r" % cachepath)
                
    def get_headfilelink(self):
        """ Get the link url to this head file. """
        cachepath = self.get_cachepath()
        if os.path.isfile(cachepath):
            # The file exist in media path -> Let the webserver send this file ;)
            url = posixpath.join(
                settings.MEDIA_URL, settings.PYLUCID.PYLUCID_MEDIA_DIR, settings.PYLUCID.CACHE_DIR,
                self.filepath
            )
        else:
            # not cached into filesystem -> use pylucid.views.send_head_file for it
            url = reverse('PyLucid-send_head_file', kwargs={"filepath":self.filepath})
        return headfile.HeadfileLink(url)

    def auto_mimetype(self):
        """ returns the mimetype for the current filename """
        fileext = os.path.splitext(self.filepath)[1].lower()
        if fileext == ".css":
            return u"text/css"
        elif fileext == ".js":
            return u"text/javascript"
        else:
            mimetypes.guess_type(self.filepath)[0] or u"application/octet-stream"

    def save(self, *args, **kwargs):
        if not self.mimetype:
            # autodetect mimetype
            self.mimetype = self.auto_mimetype()

        # Try to cache the head file into filesystem (Only worked, if python process has write rights)
        self.save_cache_file()

        return super(EditableHtmlHeadFile, self).save(*args, **kwargs)

    def __unicode__(self):
        return u"EditableHtmlHeadFile '%s'" % self.filepath

    class Meta:
        ordering = ("filepath",)


class UserProfileManager(UpdateInfoBaseModelManager):
    def create_user_profile(self, request, user):
        userprofile, created = self.get_or_create(request, user=user)
        if created:
            request.user.message_set.create(
                message="UserProfile entry for user '%s' created." % user
            )
        
        if not user.is_superuser:
            # Info: superuser can automaticly access all sites
            site = Site.objects.get_current()
            userprofile.site.add(site)
            request.user.message_set.create(
                message="Add site '%s' to '%s' UserProfile." % (site.name, user)
            )
            
    def delete(self, request, user):
        userprofile = self.get(user=user)
        userprofile.delete()
        request.user.message_set.create(
            message="UserProfile entry from user '%s' deleted." % user
        )

    
class UserProfile(UpdateInfoBaseModel):
    """
    Stores additional information about PyLucid users
    http://docs.djangoproject.com/en/dev/topics/auth/#storing-additional-information-about-users
    
    We hacked into django.contrib.auth.admin.UserAdmin in pylucid/admin.py for
    create/delete UserProfile entries.
    """
    objects = UserProfileManager()

    user = models.ForeignKey(User, unique=True, related_name="%(class)s_user")
    
    sha_login_checksum = models.CharField(max_length=192,
        help_text="Checksum for PyLucid JS-SHA-Login"
    )
    sha_login_salt = models.CharField(max_length=5,
        help_text="Salt value for PyLucid JS-SHA-Login"
    )
    
    site = models.ManyToManyField(Site,
        help_text="User can access only these sites."
    )

    def __unicode__(self):
        return u"UserProfile for user '%s'" % self.user.username

    def site_info(self):
        """ for pylucid.admin.UserProfileAdmin.list_display """
        sites = self.site.all()
        return ", ".join([site.name for site in sites])
    
    class Meta:
        ordering = ("user",)
