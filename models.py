from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Date,
    Numeric, Boolean
)
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(100), unique=True, nullable=False)

    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("Role", back_populates="users")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    supplier_name = Column(String(150), nullable=False)
    contact_person = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(20), nullable=False)
    address = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(150), nullable=False)
    sku = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    category = Column(String(100))
    unit_price = Column(Numeric(10, 2), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    has_expiry = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    supplier = relationship("Supplier")
    batches = relationship("InventoryBatch", back_populates="product")


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    batch_number = Column(String(100), unique=True, nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    received_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    expiry_date = Column(Date, nullable=True)

    product = relationship("Product", back_populates="batches")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False)
    customer_name = Column(String(150), nullable=False)

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=True
    )

    bundle_id = Column(
        Integer,
        ForeignKey("product_bundles.id"),
        nullable=True
    )

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), default="Pending")
    order_date = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")
    bundle = relationship("ProductBundle")

    batch_allocations = relationship(
        "OrderBatchAllocation",
        back_populates="order",
        cascade="all, delete-orphan"
    )
class OrderBatchAllocation(Base):
    __tablename__ = "order_batch_allocations"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("inventory_batches.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="batch_allocations")
    batch = relationship("InventoryBatch")


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    shipment_number = Column(String(50), unique=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True, nullable=False)
    carrier_name = Column(String(150), nullable=False)
    tracking_number = Column(String(100), unique=True, nullable=False)
    shipment_status = Column(String(50), default="Processing")
    shipment_date = Column(DateTime, default=datetime.utcnow)
    delivery_date = Column(DateTime, nullable=True)

    order = relationship("Order")


class ProductBundle(Base):
    __tablename__ = "product_bundles"

    id = Column(Integer, primary_key=True, index=True)
    bundle_name = Column(String(150), nullable=False)
    bundle_sku = Column(String(100), unique=True, nullable=False)
    bundle_price = Column(Numeric(10, 2), nullable=False)

    items = relationship(
        "BundleItem",
        cascade="all, delete-orphan"
    )

class BundleItem(Base):
    __tablename__ = "bundle_items"

    id = Column(Integer, primary_key=True, index=True)

    bundle_id = Column(
        Integer,
        ForeignKey("product_bundles.id"),
        nullable=False
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False
    )

    quantity = Column(Integer, nullable=False)

    product = relationship("Product")