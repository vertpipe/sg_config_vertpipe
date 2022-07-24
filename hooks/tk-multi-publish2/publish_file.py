# Copyright (c) 2018 MythVFX

import os
import sys
import traceback

import difflib
import pprint

import sgtk
from sgtk.util.filesystem import copy_folder, copy_file, ensure_folder_exists
from sgtk.platform.qt import QtCore, QtGui
HookBaseClass = sgtk.get_hook_baseclass()

class PublishFile(HookBaseClass):
    """
    Plugin for publishing any random reference file via the standalone Publisher.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/publish_file.py:{config}/tk-multi-publish2/publish_file.py"

    """
    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to recieve
        through the settings parameter in the accept, validate, publish and
        finalize methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts
        as part of its environment configuration.
        """

        # inherit the settings from the base publish plugin
        base_settings = \
            super(PublishFile, self).settings or {}
        return {
            "Element Name": {
                "type": "str",
                "default": "",
                "description": "Element name setting."
            },
            "File Types": {
                "type": "list",
                "default": [
                    ["Alembic Cache", "abc"],
                    ["3dsmax Scene", "max"],
                    ["NukeStudio Project", "hrox"],
                    ["Houdini Scene", "hip", "hipnc"],
                    ["Maya Scene", "ma", "mb"],
                    ["Motion Builder FBX", "fbx"],
                    ["Nuke Script", "nk"],
                    ["Photoshop Image", "psd", "psb"],
                    ["Rendered Image", "dpx", "exr"],
                    ["Texture", "tiff", "tx", "tga", "dds"],
                    ["Image", "jpeg", "jpg", "png"],
                    ["Movie", "mov", "mp4"],
                ],
                "description": (
                    "List of file types to include. Each entry in the list "
                    "is a list in which the first entry is the Shotgun "
                    "published file type and subsequent entries are file "
                    "extensions that should be associated."
                )
            },
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published work files. Should"
                               "correspond to a template defined in "
                               "templates.yml.",
            }
        }

        # update the base settings
        base_settings.update(base_publish_settings)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """
        return ["file.*", "folder.*"]

    def _copy_work_to_publish(self, settings, item):
        """
        This method handles copying work file path(s) to a designated publish
        location.

        This method requires a "work_template" and a "publish_template" be set
        on the supplied item.

        The method will handle copying the "path" property to the corresponding
        publish location assuming the path corresponds to the "work_template"
        and the fields extracted from the "work_template" are sufficient to
        satisfy the "publish_template".

        The method will not attempt to copy files if any of the above
        requirements are not met. If the requirements are met, the file will
        ensure the publish path folder exists and then copy the file to that
        location.

        If the item has "sequence_paths" set, it will attempt to copy all paths
        assuming they meet the required criteria with respect to the templates.

        """

        # ---- ensure templates are available

        publish_template = self.get_publish_template(settings, item)
        if not publish_template:
            self.logger.debug(
                "No publish template set on the item. "
                "Skipping copying file to publish location."
            )
            return

        # ---- get a list of files to be copied

        # by default, the path that was collected for publishing
        sequence_files = [item.properties.path]

        # if this is a sequence, get the attached files
        if "sequence_paths" in item.properties:
            sequence_files = item.properties.get("sequence_paths", [])
            if not sequence_files:
                self.logger.warning(
                    "Sequence publish without a list of files. Publishing "
                    "the sequence path in place: %s" % (item.properties.path,)
                )
                return

        # ---- copy the work files to the publish location

        for sequence_file in sequence_files:
            #TODO: this is a kinda ugly way to get current frame.   We might be better of adding a get_frame() method to a hook util
            sequence_spec = self.parent.util.get_frame_sequence_path( sequence_file, frame_spec='####')
            if sequence_spec is not None:
                seqm = difflib.SequenceMatcher(None, sequence_file, sequence_spec)
                diff = filter(lambda x:x[0] == 'replace', seqm.get_opcodes())[0]
                frame = int(seqm.a[diff[1]:diff[2]])
                item.properties["current_frame"] = frame

            publish_file = self._get_publish_path(settings, item)

            # copy the file
            try:
                publish_folder = os.path.dirname(publish_file)
                ensure_folder_exists(publish_folder)
                if item.type.startswith('folder'):
                    copy_folder(sequence_file, publish_file)
                else:
                    copy_file(sequence_file, publish_file)
            except Exception as e:
                raise Exception(
                    "Failed to copy work file from '%s' to '%s'.\n%s" %
                    (sequence_file, publish_file, traceback.format_exc())
                )

            self.logger.debug(
                "Copied work file '%s' to publish file '%s'." %
                (sequence_file, publish_file)
            )

        if 'current_frame' in item.properties:
            del item.properties['current_frame']

        item.properties["publish_path"] = self.parent.util.get_frame_sequence_path(publish_file) or publish_file

    def _get_publish_version(self, settings, item):
        """
        Get the publish version for the supplied settings and item.

        :param settings: The publish settings defining the publish types
        :param item: The item to determine the publish version for

        Extracts the publish version via the configured work template if
        possible. Will fall back to using the path info hook.
        """

        # if we happened to have stashed a version in our properties use that
        if item.properties.get("version"):
            return item.properties.get("version")

        # version is used so we need to find the latest version - this means
        # searching for publishedFiles linked to the task...
        # need a file key to find all versions so lets build it:
        publisher = self.parent
        pf_fields = ['version_number']
        pf_filters = [["task", "is", item.context.task]]
        publishedFiles = publisher.shotgun.find('PublishedFile', filters=pf_filters, fields=pf_fields)

        max_version = max([pf['version_number'] for pf in publishedFiles] or [0])
        next_version = max_version + 1

        self.logger.info("Next publish version: %d" % next_version)
        item.properties['version'] = next_version
        return next_version

    def get_publish_path(self, settings, item):
        # if this is a sequence, use a dummy frame to get a spec path
        if "sequence_paths" in item.properties:
            # dummy frame number
            item.properties['current_frame'] = 1
        publish_file = self._get_publish_path(settings, item)
        publish_file = self.parent.util.get_frame_sequence_path(publish_file) or publish_file
        if 'current_frame' in item.properties:
            del item.properties['current_frame']
        return publish_file

    def get_publish_version(self, settings, item):
        return self._get_publish_version(settings, item)

    def _get_publish_path(self, settings, item):
        """
        Get a publish path for the supplied settings and item.

        :param settings: The publish settings defining the publish types
        :param item: The item to determine the publish type for

        :return: A string representing the output path to supply when
            registering a publish for the supplied item

        Extracts the publish path via the configured work and publish templates
        if possible.
        """
        publisher = self.parent
        self.logger.debug("running hook _get_publish_path")
        path = item.properties["path"]
        name, ext = os.path.splitext(os.path.basename(path))
        #item.properties["name"] = name
        if not item.properties.get("ext"):
            item.properties["ext"] = ext.strip('.').lower()
        work_template = item.properties.get("work_template")
        self.logger.debug("work_template = %s" % work_template)
        publish_template = item.properties.get("publish_template")
        self.logger.debug("publish_template = %s" % publish_template)
        work_fields = []
        publish_path = None
        # We need both work and publish template to be defined for template support to be enabled.
        if publish_template:
            if work_template:
                if work_template.validate(path):
                    work_fields = work_template.get_fields(path)

                missing_keys = publish_template.missing_keys(work_fields)
                if missing_keys:
                    self.logger.warning(
                        "Did you set the \'Task\' and \'Entity Link\' yet?")
                    raise Exception("Not enough keys to apply fields (%s) to "
                                    "publish template (%s)" % (work_fields, publish_template))
                else:
                    publish_path = publish_template.apply_fields(work_fields)
                    self.logger.debug(
                        "Used publish template to determine the publish path: %s" %
                        (publish_path,)
                    )
            # no work template, just a publish template so we have to get keys by some other means
            else:
                fields = {}
                context = item.context
                self.logger.debug("context %s" % (context))

                try:
                    fields = context.as_template_fields(publish_template, validate=False)
                    self.logger.debug("fields %s" % (fields))

                except Exception as e:
                    try:
                        # force creation of folders so we're able to resolve template fields
                        self.logger.debug("Unable to resolve template fields! Attempting to create filesystem structure (folders).")
                        task = context.task
                        context.tank.create_filesystem_structure(task['type'], task['id'])
                        fields = context.as_template_fields(publish_template, validate=False)
                    except Exception as e:
                        # and raise a new, clearer exception for this specific use case:
                        raise Exception("Unable to resolve template fields!  This could mean there is a mismatch "
                                        "between your folder schema and templates.  Please email "
                                        "help.pipeline@mythvfx.com if you need help fixing this.")

                        # it's ok not to have a path preview at this point!
                        return {}

                version_is_used = "version" in publish_template.keys
                if version_is_used:
                    # update version:
                    fields["version"] = self._get_publish_version(settings, item)

                if settings['Element Name'].value != '':
                    fields["name"] = settings['Element Name'].value

                if item.properties["ext"]:
                    fields["ext"] = item.properties["ext"]

                if item.properties.get('Installment'):
                    fields["Installment"] = item.properties.get('Installment')

                fields["seq_frame"] = item.properties.get("current_frame")

                if item.type.startswith('file.image'):
                    width, height = self._get_publish_img_dimensions(settings, item)
                    fields["width"] = width
                    fields["height"] = height

                missing_keys = publish_template.missing_keys(fields)
                # sometimes keys are missing even though they're defined with default values
                for missing_key in missing_keys:
                    if publish_template.keys[missing_key].default:
                        fields[missing_key] = publish_template.keys[missing_key].default
                        missing_keys.remove(missing_key)

                if missing_keys:
                    self.logger.debug("missing keys: %s" % missing_keys)
                    self.logger.warning(
                        "Did you set the \'Task\' and \'Entity Link\' yet?")

                    raise Exception("Not enough keys to apply fields (%s) to "
                        "publish template (%s)" % (fields, publish_template))
                else:
                    publish_path = publish_template.apply_fields(fields)
                    self.logger.debug(
                        "Used publish template to determine the publish path: %s" %
                        (publish_path,)
                    )
        else:
            self.logger.debug("publish_template: %s" % publish_template)
            self.logger.debug("work_template: %s" % work_template)


        if not publish_path:
            publish_path = path
            self.logger.debug(
                "Could not validate a publish template. Publishing in place.")

        return publish_path

    def _get_publish_img_dimensions(self, settings, item):
        if item.properties.get("width") and item.properties.get("height"):
            return item.properties["width"], item.properties["height"]

        # by default, the path that was collected for publishing
        sequence_files = [item.properties.path]

        # if this is a sequence, get the attached files
        if "sequence_paths" in item.properties:
            sequence_files = item.properties.get("sequence_paths", [])
            if not sequence_files:
                self.logger.warning(
                    "Sequence publish without a list of files. Publishing "
                    "the sequence path in place: %s" % (item.properties.path,)
                )
                return

        # ---- load PIL from our framework and check image dimensions
        self.load_framework("tk-framework-imageutils_v0.x.x")
        from PIL import Image
        sequence_first_img = Image.open(sequence_files[0])
        item.properties["width"] = sequence_first_img.width
        item.properties["height"] = sequence_first_img.height
        return item.properties["width"], item.properties["height"]

    def accept(self, settings, item):
        """
        all the factory logic except we want to allow context switching during publish
        """
        # run the base class acceptance
        return_val = super(PublishFile, self).accept(
            settings, item)

        # re-enable context changing since the base class disabled it
        item.context_change_allowed = True

        # if we arrived at an element 'name' during collection plug that into our settings now
        if item.properties.get('name'):
            settings["Element Name"].value = str(item.properties.get('name'))

        return return_val

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.

        Returns a boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: True if item is valid, False otherwise.
        """

        path = item.properties["path"]
        name = os.path.splitext(os.path.basename(path))[0]
        self.logger.debug("name: %s" % name)
        item.properties["name"] = name

        # populate the publish template on the item if found
        publisher = self.parent
        publish_template_setting = settings.get("Publish Template")
        # we're now supporting lists of templates on standalone publish
        # the first one in the list that is viable wins (per item)
        if isinstance(publish_template_setting.value, list):
            template_match = False
            for publish_template_name in publish_template_setting.value:
                publish_template = publisher.engine.get_template_by_name(
                    publish_template_name)
                if publish_template:
                    item.properties["publish_template"] = publish_template
                    # the best test is to see if we get a valid publish path
                    try:
                        if self._get_publish_path(settings, item):
                            template_match = True
                            break
                    except:
                        pass
             # if we got to this point none of the templates in our list were viable
            # raise an exception now
            if not template_match:
                item.properties["publish_template"] = None
                raise Exception("Unable to match to a viable publish template out of list: %s" % publish_template_setting.value)
        else:
            publish_template = publisher.engine.get_template_by_name(
                publish_template_setting.value)
            if publish_template:
                item.properties["publish_template"] = publish_template

        self.logger.info("using publish template: %s" % item.properties["publish_template"])
        # run the base class validation
        return super(PublishFile, self).validate(
            settings, item)

    def create_settings_widget(self, parent):

        qtwidgets = self.load_framework("tk-framework-qtwidgets_v2.x.x")

        return CustomNameWidget(
            parent,
            qtwidgets,
            description_widget=super(PublishFile, self).create_settings_widget(parent),
        )

    def get_ui_settings(self, widget):

        settings = {}
        settings["Element Name"] = str(widget.editLine.text())
        return settings

    def set_ui_settings(self, widget, tasks_settings):
        if len(tasks_settings) > 1:
            raise NotImplementedError

        widget.editLine.setText(tasks_settings[0]["Element Name"])

class CustomNameWidget(QtGui.QWidget):

    def __init__(self, parent, qtwidgets, description_widget=None):
        QtGui.QWidget.__init__(self, parent)

        layout = QtGui.QVBoxLayout(self)

        ## Label
        self.label = QtGui.QLabel(self)
        self.label.setText("Element Name")
        layout.addWidget(self.label)

        ## Line edit
        self.editLine = QtGui.QLineEdit(self)

        ## only allow alphanumeric
        rx = QtCore.QRegExp("[a-zA-Z0-9]{0,32}")
        validator = QtGui.QRegExpValidator(rx, self)
        self.editLine.setValidator(validator)

        ## Layout
        layout.addWidget(self.editLine)

        self.setLayout(layout)

        if description_widget:
            layout.addWidget(description_widget)

        #elided_label = qtwidgets.import_module("elided_label")
        #long_label = elided_label.ElidedLabel(self)
        #long_label.setText("why do we need a long label?")
        #layout.addWidget(long_label)