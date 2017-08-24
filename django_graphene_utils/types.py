import graphene

__all__ = ['FormError']

"""
Form error type
"""


class FormError(graphene.ObjectType):
    key = graphene.String()
    message = graphene.String()
