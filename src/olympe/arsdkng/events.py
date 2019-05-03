# -*- coding: UTF-8 -*-

#  Copyright (C) 2019 Parrot Drones SAS
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the Parrot Company nor the names
#    of its contributors may be used to endorse or promote products
#    derived from this software without specific prior written
#    permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
#  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
#  PARROT COMPANY BE LIABLE FOR ANY DIRECT, INDIRECT,
#  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
#  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
#  OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
#  AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
#  OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
#  SUCH DAMAGE.


from __future__ import unicode_literals
from __future__ import absolute_import

from boltons.dictutils import OrderedMultiDict
from collections import OrderedDict
from datetime import datetime
from itertools import chain
from uuid import uuid4
from yapf.yapflib.yapf_api import FormatCode
from yapf.yapflib.style import CreateFacebookStyle

from olympe.arsdkng.event_marker import EventMarker


class ArsdkMessageEvent(object):

    def __init__(self, message, args, policy=None):
        self._message = message
        self._args = args
        self._policy = policy
        self._uuid = uuid4()
        self._date = datetime.now()

    @property
    def message(self):
        return self._message

    @property
    def args(self):
        return self._args

    @property
    def policy(self):
        return self._policy

    @property
    def uuid(self):
        return self._uuid

    def __str__(self):
        ret = (self.message.fullName + "(")
        if isinstance(self.args, (list)):
            if len(self.args) == 1:
                ret += self._str_args()
            elif len(self.args):
                ret += "["
                for args in self.args:
                    ret += self._str_args()
                ret += "]"
        else:
            ret += self._str_args()
        ret += ")"
        return ret

    def _str_args(self):
        args_list = []
        for argname, argvalue in self.args.items():
            args_list += ["{}={}".format(argname, self._str_arg(argvalue))]
        if self.policy is not None:
            args_list += ["policy={}".format(self.policy)]
        return ", ".join(args_list)

    def _str_arg(self, argvalue):
        if hasattr(argvalue, 'pretty'):
            return argvalue.pretty()
        elif isinstance(argvalue, str):
            return "'" + argvalue + "'"
        else:
            return str(argvalue)


_olympe_dsl_style = CreateFacebookStyle()
_olympe_dsl_style.update(
    column_limit=100,
    split_before_dot=False,
    split_before_bitwise_operator=True,
    split_before_first_argument=True,
)


def _format_olympe_dsl(code):
    try:
        return FormatCode(code, style_config=_olympe_dsl_style)[0]
    except Exception:
        # Fallback, return unformatted olympe dsl code
        return code


class ArsdkEventContext(object):

    def __init__(self, event_list=None, policy=None, marker=None):
        if event_list is None:
            event_list = []
        if policy is not None:
            for event in event_list:
                event._policy = policy
        self._marker = marker
        self._by_uuid = OrderedDict(
            zip(map(lambda e: e.uuid, event_list), event_list))
        self._by_message_id = OrderedMultiDict(
            zip(map(lambda e: e.message.id, self._by_uuid.values()), self._by_uuid.values()))

    def events(self):
        return list(self._by_uuid.values())

    def __iter__(self):
        return iter(self._by_uuid.values())

    def _set_marker(self, marker):
        self._marker = marker
        return self

    def filter(self, message):
        if message.id in self._by_message_id:
            events = self._by_message_id.getlist(message.id)[:]
            return ArsdkEventContext(events, marker=self._marker)
        else:
            return ArsdkEventContext()

    def last(self, message=None):
        if message is None:
            return next(reversed(self._by_uuid.values()), None)
        else:
            return self._by_message_id.get(message.id)

    def __bool__(self):
        return len(self._by_uuid) > 0

    __nonzero__ = __bool__

    def _marker_prefix_str(self):
        return self._marker.begin() if self._marker is not None else ""

    def _marker_suffix_str(self):
        return self._marker.end() if self._marker is not None else ""

    def _to_str(self):
        ret = ""
        if len(self._by_uuid.values()) > 1:
            ret += "["
        for i, message_event in enumerate(self._by_uuid.values()):
            ret += self._marker_prefix_str()
            ret += str(message_event)
            ret += self._marker_suffix_str()
            if i != (len(self._by_uuid.values()) - 1):
                ret += ","
        if len(self._by_uuid.values()) > 1:
            ret += "]"
        return ret

    def __str__(self):
        return EventMarker.color_string(_format_olympe_dsl(self._to_str()))


class ArsdkMultipleEventContext(ArsdkEventContext):

    def __init__(self, contexts, combine_method, policy=None, marker=None):
        self._contexts = list(contexts)
        self._combine_method = " {} ".format(combine_method)
        super(ArsdkMultipleEventContext, self).__init__(
            list(chain.from_iterable(
                map(lambda c: c.events(), self._contexts))),
            policy=policy,
            marker=marker)

    @property
    def contexts(self):
        return list(filter(lambda c: bool(c), self._contexts))

    def _set_marker(self, marker):
        super(ArsdkMultipleEventContext, self)._set_marker(marker)
        for context in self._contexts:
            context._set_marker(marker)
        return self

    def _to_str(self):
        if len(self.contexts) == 1:
            return self.contexts[0]._to_str()
        elif len(self._contexts) != 0:
            return (
                "( " + self._combine_method.join(map(lambda c: c._to_str(), self.contexts)) + " )")
        else:
            return ""

    def __str__(self):
        return EventMarker.color_string(_format_olympe_dsl(self._to_str()))
