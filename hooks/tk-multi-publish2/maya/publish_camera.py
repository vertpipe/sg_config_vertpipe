# coding:utf-8
# /usr/bin/env python


"""
@version: ??
@author: reliable-天
@contact: U{johnny.zxt@gmail.com<johnny.zxt@gmail.com>}
@site: https://www.zxto.top:1580
@software: PyCharm
@file: publish_camera.py
@time: 2020/9/27 0:27
"""

import fnmatch
import os

import maya.cmds as cmds
import maya.mel as mel

import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class MayaCameraPublishPlugin(HookBaseClass):

    @property
    def description(self):

        return """
        <p>这个会导出 Maya camera</p>
        """

    @property
    def settings(self):
        plugin_settings = super(MayaCameraPublishPlugin, self).settings or {}
        maya_camera_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for published camera. Should"
                               "correspond to a template defined in "
                               "templates.yml.",
            },
            "Cameras": {
                "type": "list",
                "default": ["camera*"],
                "description": "Glob-style list of camera names to publish. "
                               "Example: ['camMain', 'camAux*']."
            }
        }
        plugin_settings.update(maya_camera_publish_settings)
        return plugin_settings

    @property
    def item_filters(self):
        return ["maya.session.camera"]

    def accept(self, settings, item):
        publisher = self.parent
        template_name = settings["Publish Template"].value
        cam_name = item.properties.get("camera_name")
        cam_shape = item.properties.get("camera_shape")

        if cam_name and cam_shape:
            if not self._cam_name_matches_settings(cam_name, settings):
                self.logger.debug(
                    "Camera name %s does not match any of the configured "
                    "patterns for camera names to publish. Not accepting "
                    "session camera item." % (cam_name,)
                )
                return {"accepted": False}
        else:
            self.logger.debug(
                "Camera name or shape was set on the item properties. Not "
                "accepting session camera item."
            )
            return {"accepted": False}

        work_template = item.parent.properties.get("work_template")
        if not work_template:
            self.logger.debug(
                "A work template is required for the session item in order to "
                "publish a camera. Not accepting session camera item."
            )
            return {"accepted": False}

        publish_template = publisher.get_template_by_name(template_name)
        if publish_template:
            item.properties["publish_template"] = publish_template
            item.context_change_allowed = False
        else:
            self.logger.debug(
                "The valid publish template could not be determined for the "
                "session camera item. Not accepting the item."
            )
            return {"accepted": False}

        if not mel.eval("exists \"FBXExport\""):
            self.logger.debug(
                "Item not accepted because fbx export command 'FBXExport' "
                "is not available. Perhaps the plugin is not enabled?"
            )
            return {"accepted": False}

        return {
            "accepted": True,
            "checked": True
        }

    def validate(self, settings, item):
        path = _session_path()
        if not path:
            error_msg = "The Maya session has not been saved."
            self.logger.error(
                error_msg,
                extra=_get_save_as_action()
            )
            raise Exception(error_msg)

        path = sgtk.util.ShotgunPath.normalize(path)
        cam_name = item.properties["camera_name"]

        if not cmds.ls(cam_name):
            error_msg = (
                "Validation failed because the collected camera (%s) is no "
                "longer in the scene. You can uncheck this plugin or create "
                "a camera with this name to export to avoid this error." %
                (cam_name,)
            )
            self.logger.error(error_msg)
            raise Exception(error_msg)

        work_template = item.parent.properties.get("work_template")
        publish_template = item.properties.get("publish_template")

        work_fields = work_template.get_fields(path)

        work_fields["name"] = cam_name

        missing_keys = publish_template.missing_keys(work_fields)
        if missing_keys:
            error_msg = "Work file '%s' missing keys required for the " \
                        "publish template: %s" % (path, missing_keys)
            self.logger.error(error_msg)
            raise Exception(error_msg)

        publish_path = publish_template.apply_fields(work_fields)
        item.properties["path"] = publish_path
        item.properties["publish_path"] = publish_path

        if "version" in work_fields:
            item.properties["publish_version"] = work_fields["version"]

        return super(MayaCameraPublishPlugin, self).validate(settings, item)

    def publish(self, settings, item):
        cur_selection = cmds.ls(selection=True)
        cam_shape = item.properties["camera_shape"]
        cmds.select(cam_shape)
        publish_path = item.properties["publish_path"]
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)
        fbx_export_cmd = 'FBXExport -f "%s" -s' % (publish_path.replace(os.path.sep, "/"),)

        try:
            self.logger.debug("Executing command: %s" % fbx_export_cmd)
            mel.eval(fbx_export_cmd)
        except Exception as e:
            self.logger.error("Failed to export camera: %s" % e)
            return

        super(MayaCameraPublishPlugin, self).publish(settings, item)
        cmds.select(cur_selection)

    def _cam_name_matches_settings(self, cam_name, settings):
        cam_patterns = settings["Cameras"].value
        if not cam_patterns:
            return True

        for camera_pattern in cam_patterns:
            if fnmatch.fnmatch(cam_name, camera_pattern):
                return True

        return False


def _session_path():
    path = cmds.file(query=True, sn=True)

    if isinstance(path, bytes):
        path = path.encode("utf-8")

    return path


def _get_save_as_action():
    engine = sgtk.platform.current_engine()
    callback = cmds.SaveScene
    if "tk-multi-workfiles2" in engine.apps:
        app = engine.apps["tk-multi-workfiles2"]
        if hasattr(app, "show_file_save_dlg"):
            callback = app.show_file_save_dlg

    return {
        "action_button": {
            "label": "Save As...",
            "tooltip": "Save the current session",
            "callback": callback
        }
    }