from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


class Token(Base):
    __tablename__ = 'token'

    id = Column(Integer, primary_key=True)
    token_value = Column(String, nullable=False)
    valid_until = Column(Text, nullable=False)
    uses_left = Column(Integer, nullable=False)
    assigned_group = Column(String)
    assigned_group_id = Column(String)


class DatabaseAdapter:
    def __init__(self, db: str):
        self.engine = create_engine(f'sqlite:///{db}', echo=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def insert_token(self, token_value: str, valid_until: str, uses_left: int, assigned_group: str = None,
                     assigned_group_id: str = None):
        session = self.Session()
        new_token = Token(token_value=token_value, valid_until=valid_until, uses_left=uses_left,
                          assigned_group=assigned_group, assigned_group_id=assigned_group_id)
        session.add(new_token)
        session.commit()
        session.close()

    def remove_token(self, token_value):
        session = self.Session()
        session.query(Token).filter_by(token_value=token_value).delete()
        session.commit()
        session.close()

    def remove_all_tokens(self):
        session = self.Session()
        session.query(Token).delete()
        session.commit()
        session.close()

    def select_token(self, token_value):
        session = self.Session()
        token = session.query(Token).filter_by(token_value=token_value).first()
        session.close()
        return token

    def select_token_by_id(self, token_id):
        session = self.Session()
        token = session.query(Token).filter_by(id=token_id).first()
        session.close()
        return token

    def select_all_tokens(self):
        session = self.Session()
        tokens = session.query(Token).all()
        session.close()
        return tokens

    def update_token_uses(self, token_value):
        session = self.Session()
        token = session.query(Token).filter_by(token_value=token_value).first()
        token.uses_left -= 1
        session.commit()
        session.close()
        return token
