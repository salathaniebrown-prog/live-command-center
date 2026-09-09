from setuptools import find_packages, setup


setup(
    name="bci-analytics",
    version="1.0.0",
    description="Deterministic multi-domain telemetry analytics framework",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.22.0",
    ],
    entry_points={
        "console_scripts": [
            "run-telemetry=bci_analytics.engine:main",
        ],
    },
)
