from setuptools import setup

setup(
    name='getquote',
    version='0.0.6',
    author='Ashish Agnihotri',
    author_email='your.email@example.com',
    description='A sample Python script',
    install_requires=[
        'requests'
    ],
    entry_points={
        'console_scripts': [
            'getquote=getquote:main'
        ]
    },
)
