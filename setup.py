from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="nmbs-train-data-api",
    version="0.2.0",
    author="NMBS Train Data API Team",
    author_email="Sander.truyts@gmail.com",
    description="API for accessing Belgian railways (NMBS/SNCB) real-time and planning data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DubblePumper/NMBS-Train-Data-API",
    project_urls={
        "Bug Tracker": "https://github.com/DubblePumper/NMBS-Train-Data-API/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "gtfs-realtime-bindings>=1.0.0",
        "protobuf>=3.20.0",
        "beautifulsoup4>=4.10.0",
        "requests>=2.27.0",
        "python-dotenv>=1.0.0",
        "cloudscraper>=1.2.71",
        "schedule>=1.1.0",
        "flask>=2.0.0",
        "flask-cors>=3.0.10",
        "lxml>=4.9.0",  # For better HTML parsing with BeautifulSoup
        "charset-normalizer",  # For better character encoding detection
        "pandas>=1.3.0",    # For parsing CSV and TXT files
    ],
    entry_points={
        "console_scripts": [
            "nmbs-data-service=nmbs_api.cli.service_runner:main",
            "nmbs-web-api=nmbs_api.cli.web_runner:main",
        ],
    },
)