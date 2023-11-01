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
$ mkdir fastgql-tutorial
// Enter into that directory
$ cd fastgql-tutorial
```

</div>

Make sure you don't name it also `fastgql`, so that you don't end up overriding the name of the package.

### Make sure you have Python

Make sure you have an officially supported version of Python.

You can check which version you have with:

<div class="termy">

```console
$ python3 --version
Python 3.12
```

</div>

For now, FastGQL only supports python 3.10 and up.

If you don't have python 3.10 or up installed, go and install that first.

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
    // The important part is that it is inside the project directory, at "code/fastgql-tutorial/env/bin/python"
    /home/leela/code/fastgql-tutorial/env/bin/python
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
    // The important part is that it is inside the project directory, at "code\fastgql-tutorial\env\python.exe"
    CommandType    Name    Version     Source
    -----------    ----    -------     ------
    Application    python  0.0.0.0     C:\Users\leela\code\fastgql-tutorial\env\python.exe
    // Use the module "pip" to install and upgrade the package "pip" 🤯
    # (env) >$ python3 -m pip install --upgrade pip
    ---> 100%
    Successfully installed pip
    ```

    </div>

## Install **FastGQL**

Now, after making sure we are inside of a virtual environment in some way, we can install **FastGQL**:

<div class="termy">

```console
# (env) $$ python -m pip install fastgql
---> 100%
Successfully installed fastgql
```

</div>
