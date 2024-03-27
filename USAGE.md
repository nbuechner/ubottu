# Ubottu Commands

This documentation outlines the usage of commands supported by the bot. The bot reacts to commands prefixed with `!`. Below are the available commands and their descriptions:

## Factoids / Facts

This is a dynamic list of replies.
The available facts are available at [here](https://maubot.haxxors.com/factoids/). You can make [suggestions](https://cloud.haxxors.com/s/Yr7GEfDazHSC8gH) for additional facts.

**Usage**: `!fact_name [| username])`

**Example 1**:`!noble`

**Response**: `Ubuntu 24.04 (Noble Numbat) will be the 40th release of...`

**Example 2**: `!noble | Bob`

**Response**: `Bob: Ubuntu 24.04 (Noble Numbat) will be the 40th...`

## Launchpad Bugs

The bot reacts to URLs from bugs.launchpad.net and to "bug [#]bugnumber" in messages.

**Example 1**: got this issue right now https://bugs.launchpad.net/snapd/+bug/2052688 on my computer

**Example 2**: i am affected by bug 2052688 on my computer

**Example 3**: i am affected by bug #2052688 on my computer

**Response**: Launchpad Bug #2052688 in snapd "run-snapd-ns-snapd\x2ddesktop [...] " [Undecided, New]

## Time Commands

### `!time <city>`

Retrieves the current local time for a specified city.

**Usage**: `!time city_name`

**Example**:!time duesseldorf **Response**: The current time in Düsseldorf, Nordrhein-Westfalen, Deutschland is Friday, 22 March 2024, 19:59`

### `!utc`

Retrieves the current time in UTC timezone, displayed as the local time in London.

**Usage**: `!utc`

**Response**: `The current time in London, Greater London, England, United Kingdom is Friday, 22 March 2024, 19:00`

## Package Commands

### `!package <package_name> [<distribution>]`

Fetches package information for a specified package name and distribution.
The distribution argument is optional and defaults to "noble".

**Usage**:`!package package_name distribution`

**Example**:`!package nano jammy`

**Response**: `nano (6.2-1, jammy): Depends on libc6 (>= 2.34), libncursesw6 (>= 6), libtinfo6 (>= 6)`

### `!depends <package_name>`

Retrieves the dependencies of the specified package name, typically from the latest distribution.

**Usage**: `!depends package_name`

**Example**: `!depends nano`

**Response**: `nano (7.2-2, noble): Depends on libc6 (>= 2.38), libncursesw6 (>= 6), libtinfo6 (>= 6)`nano (7.2-2, noble)`
