#
# logger
#
# Copyright (c) 2020 Daniel Dean <dd@danieldean.uk>.
#
# Licensed under The MIT License a copy of which you should have
# received. If not, see:
#
# http://opensource.org/licenses/MIT
#

import re


class Logger:

    def __init__(self, logger, level, regex=None):
        self.logger = logger
        self.level = level
        self.regex = regex

    def write(self, message):
        if message != '\n' and not message.isspace():
            if self.regex:
                message = re.sub(self.regex, '', message)
            self.logger.log(self.level, message.rstrip())

    def flush(self):
        pass
