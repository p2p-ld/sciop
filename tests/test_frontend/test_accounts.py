def test_no_include_unapproved(dataset, upload, client, account, session):
    """Unapproved uploads are not included in dataset uploads lists"""
    ds = dataset()
    acc = account(username="newbie")
    unapproved = upload(dataset_=ds, is_approved=False, account_=acc)
    approved = upload(dataset_=ds, is_approved=True, account_=acc)
    res = client.get("/accounts/newbie/uploads", headers={"HX-Request": "true"})
    assert res.status_code == 200
    assert unapproved.infohash not in res.text
    assert approved.infohash in res.text


def test_no_include_removed(dataset, upload, client, session, account):
    """Removed uploads are not included in dataset uploads lists"""
    ds = dataset()
    acc = account(username="newbie")
    removed = upload(dataset_=ds, is_approved=True, account_=acc)
    approved = upload(dataset_=ds, is_approved=True, account_=acc)
    removed_infohash = removed.infohash
    approved_infohash = approved.infohash
    removed.is_removed = True
    session.add(removed)
    session.commit()

    res = client.get("/accounts/newbie/uploads", headers={"HX-Request": "true"})
    assert res.status_code == 200
    assert removed_infohash not in res.text
    assert approved_infohash in res.text
