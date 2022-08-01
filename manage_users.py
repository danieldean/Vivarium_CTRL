#!/usr/bin/python3

#
# manage_users
#
# Copyright (c) 2020 Daniel Dean <dd@danieldean.uk>.
#
# Licensed under The MIT License a copy of which you should have
# received. If not, see:
#
# http://opensource.org/licenses/MIT
#

import sys
import sqlite3
import hashlib
import secrets
import os

# Use paths relative to the script.
dirname = os.path.dirname(__file__)
if dirname:
    dirname += '/'

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

HELP_TEXT = """
Usage: manage_users.py <command> [<args>]

Manage users in the users table of the database. Commands:

Add a user:
    add <username> <password>
Delete a user:
    del <username>
Change a users password:
    chpwd <username> <new-password>

There is limited validation on these commands!
"""


def main(args):

    db = sqlite3.connect(dirname + '/vivarium_ctrl.db')
    c = db.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS users (username CHARACTER VARYING(20) NOT NULL, '
              'password CHARACTER(64) NOT NULL, ''salt CHARACTER(16) NOT NULL)')
    db.commit()

    if len(args) == 1:
        print("Invalid command. Try '--help'.")
    elif args[1] == 'add' and len(args) == 4:
        salt = random_salt()
        password = args[3] + salt
        c.execute('INSERT INTO users VALUES (?, ?, ?)',
                  (args[2], hashlib.sha256(password.encode('utf-8')).hexdigest(), salt))
        db.commit()
        print("User with username '" + args[2] + "' added.")
    elif args[1] == 'del' and len(args) == 3:
        c.execute('DELETE FROM users WHERE username=?', (args[2], ))
        db.commit()
        print("User with username '" + args[2] + "' removed.")
    elif args[1] == 'chpwd' and len(args) == 4:
        salt = random_salt()
        password = args[3] + salt
        c.execute('UPDATE users SET password=?, salt=? WHERE username=?',
                  (hashlib.sha256(password.encode('utf-8')).hexdigest(), salt, args[2]))
        db.commit()
        print("Password changed for user with username '" + args[2] + "'.")
    elif args[1] == '--help':
        print(HELP_TEXT)
    else:
        print("Invalid command. Try '--help'.")

    db.close()


def random_salt():
    chars = []
    for i in range(16):
        chars.append(secrets.choice(ALPHABET))
    return ''.join(chars)


if __name__ == "__main__":
    main(sys.argv)
