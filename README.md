# Ubottu Matrix Helper Bot

The bot is a plugin for [Maubot](https://github.com/maubot/maubot). Please see their documentation for [setup](https://docs.mau.fi/maubot/usage/setup/index.html) and [development](https://docs.mau.fi/maubot/dev/getting-started.html).
See [USAGE.md](https://git.buechner.me/nbuechner/ubottu/src/branch/main/USAGE.md) for supported commands.
There is a Django [web component](https://git.buechner.me/nbuechner/ubottu-web) that provides the API for most of the bot's features.

## Building

### Clone the Repository

To clone the repository, use the following command:

```bash
git clone https://git.buechner.me/nbuechner/ubottu.git
```

### Navigate to the Directory

Change your current working directory to the cloned repository:

```bash
cd ubottu
```

### Create a Python Virtual Environment

Create a virtual environment for the project:

```bash
python3 -m venv .venv
```

### Activate the Virtual Environment

Activate the created virtual environment:

```bash
source .venv/bin/activate
```

### Install Dependencies

Install the required dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Build the module

```bash
mbc build
```

This produces a .mbp file you can upload via the Maubot admin interface.
