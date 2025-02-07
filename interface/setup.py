import setuptools

runtime_requirements = ["pydantic>=2,<3"]

# For running tests, linting, etc
dev_requirements = ["mypy", "pytest", "black"]

# Should always be the same as the nora_lib version
version = open("version.txt").read().strip()

setuptools.setup(
    name="nora_lib",
    version=version,
    description="For making and coordinating agents and tools",
    url="https://github.com/allenai/nora_lib/interface",
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src", include=["nora_lib*"], exclude=["nora_lib.impl*"]),
    install_requires=runtime_requirements,
    package_data={
        "nora_lib": ["py.typed"],
    },
    extras_require={
        "dev": dev_requirements,
    },
    python_requires=">=3.9",
)
