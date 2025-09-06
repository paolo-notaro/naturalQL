import streamlit as st
import duckdb

st.write("duckdb:", duckdb.__version__)
con = duckdb.connect(":memory:")
st.dataframe(con.execute("select 1 as x").df())
