"""Setup configuration for the Imentiv Python SDK."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="imentiv",
    version="0.1.0",
    author="Imentiv",
    author_email="support@imentiv.ai",
    description="Python SDK for Imentiv AI API - emotion detection and video analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/imentiv/imentiv-python-sdk",
    packages=find_packages(exclude=["tests*", "examples*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.31.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
            "types-requests",
        ],
    },
    keywords="imentiv emotion ai video analysis face detection sentiment",
)
