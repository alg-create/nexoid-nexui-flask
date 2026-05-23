'''setup.py'''
import setuptools

setuptools.setup(
    name="nexui-demo",
    version="0.0.1",
    author="Aleksy Grabowski",
    author_email="huruf@gmail.com",
    description="Nexo-in-the-cloud demo",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Development Status :: 1 - Planning",
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'flask',
        'flask-socketio',
        'pynng',
        'asn1tools',
        'babel',
        'bitstring',
        'python-dateutil',
        'timebudget'
    ],
    python_requires='>=3.6',
)
