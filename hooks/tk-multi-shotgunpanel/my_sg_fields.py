#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author : reliable-天
# @Contact : U{johnny.zxt@gmail.com<johnny.zxt@gmail.com>}
# @Website : http://zxto.top:1580
# @Gitlab  : http://zxto.top:30000
# @Time : 2022/7/6 22:01
# @File : my_sg_fields.py
# @Description :

import sgtk
import os

HookBaseClass = sgtk.get_hook_baseclass()


class ShotgunFields(HookBaseClass):

    def get_main_view_definition(self, entity_type):

        values = {
            "title": "{type} {code}",
            "body": "Status: {sg_status_list}<br>Description: {description}",
        }

        if entity_type == "Task":
            values["title"] = "Task {content}"
            values[
                "body"
            ] = """
                <big>Status: {sg_status_list}</big><br>
                {entity::showtype[<br>]}
                {[Assigned to: ]task_assignees[<br>]}
                {[<strong>Starts: </strong>]start_date}{[<strong> Due: </strong>]due_date[<br>]}
                <strong>Description: </strong><em>{sg_description}</em>
                """
        return values

