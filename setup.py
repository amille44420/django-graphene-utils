from setuptools import setup

with open('README.rst', 'r') as f:
    long_description = f.read()

setup(
    name='django-graphene-utils',
    version='0.0.1',
    description='Bunch of utilities to play with django & graphene-django',
    long_description=long_description,
    url='https://github.com/amille44420/django-graphene-utils',
    author='Adrien Mille',
    author_email='adrien.mille.aer@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Framework :: Django',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='django graphene utils',
    packages=['django_graphene_utils'],
    install_requires=['django', 'django-graphene'],
    python_requires='>=3.5',
)
