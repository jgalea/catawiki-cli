class CataError(Exception):
    pass


class Blocked(CataError):
    def __init__(self, url: str):
        self.url = url
        super().__init__(
            f"Catawiki's bot protection refused {url}. Retry in a few minutes."
        )


class ParseError(CataError):
    def __init__(self, url: str, missing: str):
        self.url = url
        self.missing = missing
        super().__init__(
            f"{url} did not contain {missing}; Catawiki's page shape may have changed"
        )


class NotFound(CataError):
    def __init__(self, url: str):
        self.url = url
        super().__init__(f"{url} does not exist")
