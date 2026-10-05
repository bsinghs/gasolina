-- App admin: the person who runs the app (support). Same powers as an owner,
-- listed separately on the People page and can't be changed by the owner.
-- Admins come from the API's ADMIN_EMAILS setting (applied on every start).
alter table people drop constraint if exists people_role_check;
alter table people add constraint people_role_check
    check (role in ('employee', 'manager', 'owner', 'admin'));
