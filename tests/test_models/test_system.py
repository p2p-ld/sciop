import pytest


@pytest.mark.skip(reason="TODO")
def test_generate_nginx():
    """
    Test that the nginx configurations that are generated are valid.

    Should call `nginx -t` to actually externally validate them across a range of parameters
    but i am very hungry and not going to implement that rn
    """
    pass
