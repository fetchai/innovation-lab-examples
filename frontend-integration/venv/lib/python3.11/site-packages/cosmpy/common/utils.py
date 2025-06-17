# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2018-2022 Fetch.AI Limited
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Utils."""

import json
from typing import Any


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder subclass that encode basic python objects."""  # noqa: D401

    def default(self, o: Any) -> Any:
        """Default json encode."""  # noqa: D401
        if not hasattr(o, "__json__"):
            return super().default(o)
        if callable(o.__json__):
            return o.__json__()
        return o.__json__


def json_encode(data, **kwargs):
    """Json encode."""
    return JSONEncoder(**kwargs).encode(data)
