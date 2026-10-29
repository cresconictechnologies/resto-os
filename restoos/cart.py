#!/usr/bin/env python3
# shortcut: in-memory cart; DB commit only on settlement
CART = []

def add(sku, qty, price): CART.append({"sku":sku,"qty":qty,"price":price,"line":len(CART)+1})

def total(): return sum(i["qty"]*i["price"] for i in CART)

def clear(): CART.clear()
