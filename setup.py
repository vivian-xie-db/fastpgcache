"""
Setup script for fastpgcache
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

setup(
    name="fastpgcache",
    version="0.1.0",
    description="A fast Redis-like caching library using PostgreSQL",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Wenwen Xie",
    author_email="wenwen.xie@databricks.com",
    url="https://github.com/vivian-xie-db/fastpgcache",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        "psycopg2-binary>=2.9.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=3.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ],
        "databricks": [
            "databricks-sdk>=0.1.0",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="postgresql cache redis database caching fast performance",
    project_urls={
        "Bug Tracker": "https://github.com/vivian-xie-db/fastpgcache/issues",
        "Documentation": "https://github.com/vivian-xie-db/fastpgcache#readme",
        "Source Code": "https://github.com/vivian-xie-db/fastpgcache",
    },
)

