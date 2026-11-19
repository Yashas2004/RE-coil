import torch

from app.model import TwoTower


def test_forward_is_dot_product_of_towers():
    model = TwoTower(num_users=5, content_dim=256)
    users = torch.tensor([1, 2, 3])
    content = torch.randn(3, 256)

    logits = model(users, content)
    assert logits.shape == (3,)

    u = model.user_vectors(users)
    v = model.item_vectors(content)
    manual = (u * v).sum(dim=1)
    assert torch.allclose(logits, manual)
