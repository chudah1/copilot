from app.models.password_reset_token import PasswordResetToken


def test_password_reset_token_model_exists():
    assert PasswordResetToken.__tablename__ == "password_reset_tokens"
