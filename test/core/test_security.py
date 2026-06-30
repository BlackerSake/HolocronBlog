import pytest
from datetime import timedelta, timezone, datetime
from jose import jwt, JWTError
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from app.core.config import settings

class TestPasswordHashing:
    def test_corrent_password_and_pass(self):
        """测试 密码正确并通过"""
        password = "password"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True
    
    def test_incorrect_password_and_fail(self):
        """测试 密码错误未通过"""
        password = "password"
        hashed = get_password_hash("incorrect_password")
        assert verify_password(password, hashed) is False
    

    def test_hash_password_and_success(self):
        """测试 密码-哈希密码 成功"""
        password = "password"
        hashed = get_password_hash(password)
        assert hashed != password
    
    def test_empty_hashed_password_and_fail(self):
        """测试 密码为空未通过"""
        password = ""
        with pytest.raises(ValueError,match="密码不能为空"):
            get_password_hash(password)

    def test_hash_password_too_long_and_fail(self):
        """测试 密码太长 哈希未通过"""
        password = "wdasdajskdkjahdjkahskjdhkajshdkjashkdhaksjdhkajsdhkajsdhkjashdahofkahbskjfhqiabasvifhiojankefjs"
        with pytest.raises(ValueError,match="密码长度不能大于 72 个字符"):
            get_password_hash(password)
    
    def test_hash_password_too_short_and_fail(self):
        """测试 密码太短 哈希未通过"""
        password = "1234567"
        with pytest.raises(ValueError,match="密码长度不能小于 8 个字符"):
            get_password_hash(password)      

    def test_same_password_and_different_hash(self):
        """测试 密码相同,但生成的哈希不同"""
        password = "password"
        hashed1 = get_password_hash(password)
        hashed2 = get_password_hash(password)
        assert hashed1 != hashed2
    


class TestCreateAccessToken:

    def test_decoded_token_has_sub(self):
        """按函数签名，传入 data={"sub": "user"}，解码后应能取到"""
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        assert payload["sub"] == "testuser"

    def test_decoded_token_has_exp(self):
        """函数职责是创建带过期时间的 token，解码后应有 exp 字段"""
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        assert "exp" in payload

    def test_default_expiry_is_in_future(self):
        """不传 expires_delta 时，应使用 settings 中的默认时长，exp 须晚于当前时间"""
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        expire = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert expire > datetime.now(timezone.utc)

    def test_custom_expiry_is_respected(self):
        """参数名为 expires_delta，语义是'自定义过期时长'，应被使用而非忽略"""
        delta = timedelta(hours=2)
        now = datetime.now(timezone.utc)

        token = create_access_token({"sub": "user1"}, expires_delta=delta)
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        expire = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected = now + delta
        assert abs((expire - expected).total_seconds()) < 5

    def test_token_carries_extra_claims(self):
        """data 是 dict 类型，除 sub 外应能携带任意字段"""
        token = create_access_token({"sub": "user1", "role": "admin"})
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        assert payload["sub"] == "user1"
        assert payload["role"] == "admin"

    def test_decoding_with_wrong_secret_fails(self):
        """安全性基本要求：别人拿不到 token 内容"""
        token = create_access_token({"sub": "user1"})
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong_secret", algorithms=["HS256"])

    def test_decoding_with_wrong_algorithm_fails(self):
        token = create_access_token({"sub": "user1"})
        with pytest.raises(Exception):
            jwt.decode(token, settings.SECRET_KEY, algorithms=["HS512"])

    def test_input_data_not_mutated(self):
        """函数内部做 data.copy()，不应修改调用方传入的原 dict"""
        original = {"sub": "user1"}
        snapshot = original.copy()
        create_access_token(original)
        assert original == snapshot