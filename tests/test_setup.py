import sys

import mysql.connector
import nltk
import pandas as pd
import pytest


def test_python_version():
    assert sys.version_info >= (3, 11), "Python 3.11+ is required"


def test_required_packages_import():
    assert pd.__version__
    assert nltk.__version__


def test_mysql_connection():
    try:
        conn = mysql.connector.connect(
            host="127.0.0.1",
            port=3307,
            user="root",
            password="root",
            database="real_estate",
            connection_timeout=5,
        )
    except mysql.connector.Error as exc:
        pytest.skip(f"MySQL is not available yet: {exc}")

    try:
        assert conn.is_connected()
    finally:
        conn.close()
