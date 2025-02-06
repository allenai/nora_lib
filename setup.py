import setuptools

runtime_requirements = ["pydantic>=2,<3", "requests", "boto3", "aws_requests_auth"]

# For running tests, linting, etc
dev_requirements = ["mypy", "pytest", "black", "types-requests"]

setuptools.setup(
    name="nora_lib",
    version="0.7.1",
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
