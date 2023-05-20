# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import glob
import os
import maya.cmds as cmds
import maya.mel as mel
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()

class MyMayaSessionCollector(HookBaseClass):
    def process_current_session(self, settings, parent_item):
        super(MyMayaSessionCollector, self).process_current_session(settings, parent_item)
        session_item = next((item for item in parent_item.descendants if item.type_spec == 'maya.session'), None)
        if session_item == None:
            return

        self._collect_cameras(session_item)

    def _collect_cameras(self, parent_item):
        icon_path = os.path.join(
            self.disk_location,
            os.pardir,
            "icons",
            "camera.png"
        )
        for camera_shape in cmds.ls(cameras=True):
            try:
                camera_name = cmds.listRelatives(camera_shape, parent=True)[0]
            except Exception:
                camera_name = camera_shape
            cam_item = parent_item.create_item(
                "maya.session.camera",
                "Camera",
                camera_name
            )

            cam_item.set_icon_from_path(icon_path)
            cam_item.properties["camera_name"] = camera_name
            cam_item.properties["camera_shape"] = camera_shape
