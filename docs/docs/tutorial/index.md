# Intro, Installation, and First Steps

## Many of these sections were taken from the [SQLModel docs](https://sqlmodel.tiangolo.com/tutorial/), which are very good at explaining Python concepts. I'm including them here to make things easier.

## Type hints (From SQLModel)

If you need a refresher about how to use Python type hints (type annotations), check <a href="https://fastapi.tiangolo.com/python-types/" class="external-link" target="_blank">FastAPI's Python types intro</a>.

You can also check the <a href="https://mypy.readthedocs.io/en/latest/cheat_sheet_py3.html" class="external-link" target="_blank">mypy cheat sheet</a>.

**FastGQL** uses type annotations for everything, this way you can use a familiar Python syntax and get all the editor support possible, with autocompletion and in-editor error checking.

## Create a Project (from SQLModel)

Please go ahead and create a directory for the project we will work on on this tutorial.

What I normally do is that I create a directory named `code` inside my home/user directory.

And inside of that I create one directory per project.

So, for example:

<div class="termy">

```console
// Go to the home directory
$ cd
// Create a directory for all your code projects
$ mkdir code
// Enter into that code directory
$ cd code
// Create a directory for this project
$ mkdir sqlmodel-tutorial
// Enter into that directory
$ cd sqlmodel-tutorial
```

</div>

Make sure you don't name it also `sqlmodel`, so that you don't end up overriding the name of the package.

### Make sure you have Python

Make sure you have an officially supported version of Python.

You can check which version you have with:

<div class="termy">

```console
$ python3 --version
Python 3.12
```

</div>

For now, FastGQL only supports python 3.11 and up.

If you don't have python 3.11 or up installed, go and install that first.

### Create a Python virtual environment (from SQLModel)

When writing Python code, you should **always** use virtual environments in one way or another.

If you don't know what that is, you can read the <a href="https://docs.python.org/3/tutorial/venv.html" class="external-link" target="_blank">official tutorial for virtual environments</a>, it's quite simple.

In very short, a virtual environment is a small directory that contains a copy of Python and all the libraries you need to run your code.

And when you "activate" it, any package that you install, for example with `pip`, will be installed in that virtual environment.

!!! tip " There are other tools to manage virtual environments, like <a href="https://python-poetry.org/" class="external-link" target="_blank">Poetry</a>. "

    And there are alternatives that are particularly useful for deployment like <a href="https://docs.docker.com/get-started/" class="external-link" target="_blank">Docker</a> and other types of containers. In this case, the "virtual environment" is not just the Python standard files and the installed packages, but the whole system.

Go ahead and create a Python virtual environment for this project. And make sure to also upgrade `pip`.

Here are the commands you could use:

=== "Linux, macOS, Linux in Windows"

    <div class="termy">

    ```console
    // Remember that you might need to use python3.9 or similar 💡
    // Create the virtual environment using the module "venv"
    $ python3 -m venv env
    // ...here it creates the virtual environment in the directory "env"
    // Activate the virtual environment
    $ source ./env/bin/activate
    // Verify that the virtual environment is active
    # (env) $$ which python
    // The important part is that it is inside the project directory, at "code/sqlmodel-tutorial/env/bin/python"
    /home/leela/code/sqlmodel-tutorial/env/bin/python
    // Use the module "pip" to install and upgrade the package "pip" 🤯
    # (env) $$ python -m pip install --upgrade pip
    ---> 100%
    Successfully installed pip
    ```

    </div>

=== "Windows PowerShell"

    <div class="termy">

    ```console
    // Create the virtual environment using the module "venv"
    # >$ python3 -m venv env
    // ...here it creates the virtual environment in the directory "env"
    // Activate the virtual environment
    # >$ .\env\Scripts\Activate.ps1
    // Verify that the virtual environment is active
    # (env) >$ Get-Command python
    // The important part is that it is inside the project directory, at "code\sqlmodel-tutorial\env\python.exe"
    CommandType    Name    Version     Source
    -----------    ----    -------     ------
    Application    python  0.0.0.0     C:\Users\leela\code\sqlmodel-tutorial\env\python.exe
    // Use the module "pip" to install and upgrade the package "pip" 🤯
    # (env) >$ python3 -m pip install --upgrade pip
    ---> 100%
    Successfully installed pip
    ```

    </div>

## Install **SQLModel**

Now, after making sure we are inside of a virtual environment in some way, we can install **SQLModel**:

<div class="termy">

```console
# (env) $$ python -m pip install sqlmodel
---> 100%
Successfully installed sqlmodel pydantic sqlalchemy
```

</div>

As **SQLModel** is built on top of <a href="https://www.sqlalchemy.org/" class="external-link" target="_blank">SQLAlchemy</a> and <a href="https://pydantic-docs.helpmanual.io/" class="external-link" target="_blank">Pydantic</a>, when you install `sqlmodel` they will also be automatically installed.

## Install DB Browser for SQLite

Remember that [SQLite is a simple database in a single file](../databases.md#a-single-file-database){.internal-link target=\_blank}?

For most of the tutorial I'll use SQLite for the examples.

Python has integrated support for SQLite, it is a single file read and processed from Python. And it doesn't need an [External Database Server](../databases.md#a-server-database){.internal-link target=\_blank}, so it will be perfect for learning.

In fact, SQLite is perfectly capable of handling quite big applications. At some point you might want to migrate to a server-based database like <a href="https://www.postgresql.org/" class="external-link" target="_blank">PostgreSQL</a> (which is also free). But for now we'll stick to SQLite.

Through the tutorial I will show you SQL fragments, and Python examples. And I hope (and expect 🧐) you to actually run them, and verify that the database is working as expected and showing you the same data.

To be able to explore the SQLite file yourself, independent of Python code (and probably at the same time), I recommend you use <a href="https://sqlitebrowser.org/" class="external-link" target="_blank">DB Browser for SQLite</a>.

It's a great and simple program to interact with SQLite databases (SQLite files) in a nice user interface.

<img src="https://sqlitebrowser.org/images/screenshot.png">

Go ahead and <a href="https://sqlitebrowser.org/" class="external-link" target="_blank">Install DB Browser for SQLite</a>, it's free.

## Next Steps

Okay, let's get going! On the [next section](create-db-and-table-with-db-browser.md) we'll start creating a database. 🚀
