import setuptools

runtime_requirements = []

# For running tests, linting, etc
dev_requirements = ["mypy", "pytest", "black"]

setuptools.setup(
    name="nora_lib",
    version="0.0.1",
    description="For making and coordinating agents and tools",
    url="https://github.com/allenai/nora_lib",
    packages=setuptools.find_packages(exclude=(["tests"])),
    install_requires=runtime_requirements,
    package_data={
        "nora_lib": ["py.typed"],
    },
    extras_require={
        "dev": dev_requirements,
    },
    python_requires=">=3.9",
)
