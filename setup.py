from setuptools import setup, find_packages

setup(
    name="pokemon-doubles-meta-tracker",
    version="1.0.0",
    author="Your Name",
    description="Competitive Pokémon Doubles Meta Tracker",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
        "schedule>=1.1.0",
    ],
    entry_points={
        "console_scripts": [
            "pokemon-meta=meta_tracker:main",
        ],
    },
)
