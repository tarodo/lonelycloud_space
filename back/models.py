from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    age = Column(Integer)


class PlaylistType(Base):
    __tablename__ = "playlist_types"

    id = Column(Integer, primary_key=True, index=True)
    playlists = relationship("PlaylistHeap")


class PlaylistHeap(Base):
    __tablename__ = "playlist_heaps"

    id = Column(Integer, primary_key=True, index=True)
    type_id = Column(Integer, ForeignKey('playlist_types.id'))
    type = relationship("PlaylistType", back_populates="playlists")
