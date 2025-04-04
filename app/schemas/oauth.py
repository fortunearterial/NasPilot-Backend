from typing import Optional

from fastapi import Form, Query
from pydantic.main import BaseModel


class OAuth2AuthorizeRequestQuery(BaseModel):
    # grant_type: str = Query(default=None, regex="password")
    # state: str = Query()
    # scope: str = Query(default="read")
    # redirect_uri: str = Query()
    # client_id: str = Query()
    # client_secret: Optional[str] = Query(default=None)
    grant_type: str = None
    state: str = None
    scope: str = None
    redirect_uri: str = None
    client_id: str = None
    client_secret: Optional[str] = None


class OAuth2TokenRequestForm:
    """
    This is a dependency class, use it like:

        @app.post("/token")
        def token(form_data: OAuth2TokenRequestForm = Depends()):
            data = form_data.parse()
            print(data.username)
            print(data.password)
            for scope in data.scopes:
                print(scope)
            if data.client_id:
                print(data.client_id)
            if data.client_secret:
                print(data.client_secret)
            return data


    It creates the following Form request parameters in your endpoint:

    grant_type: the OAuth2 spec says it is required and MUST be the fixed string "password".
        Nevertheless, this dependency class is permissive and allows not passing it. If you want to enforce it,
        use instead the OAuth2PasswordRequestFormStrict dependency.
    username: username string. The OAuth2 spec requires the exact field name "username".
    password: password string. The OAuth2 spec requires the exact field name "password".
    scope: Optional string. Several scopes (each one a string) separated by spaces. E.g.
        "items:read items:write users:read profile openid"
    client_id: optional string. OAuth2 recommends sending the client_id and client_secret (if any)
        using HTTP Basic auth, as: client_id:client_secret
    client_secret: optional string. OAuth2 recommends sending the client_id and client_secret (if any)
        using HTTP Basic auth, as: client_id:client_secret
    """

    def __init__(
            self,
            grant_type: str = Form(default=None, regex="password"),
            code: str = Form(),
            code_verifier: Optional[str] = Form(default=""),
            redirect_uri: str = Form(),
            scope: Optional[str] = Form(default=""),
            client_id: Optional[str] = Form(default=None),
            client_secret: Optional[str] = Form(default=None),
    ):
        self.grant_type = grant_type
        self.code = code
        self.code_verifier = code_verifier
        self.redirect_uri = redirect_uri
        self.scopes = scope.split()
        self.client_id = client_id
        self.client_secret = client_secret
