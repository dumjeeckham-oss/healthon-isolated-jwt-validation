truncate table public.health_daily;
do $$
declare n integer;
begin
 select count(*) into n from public.health_daily;
 if n <> 0 then raise exception 'reset integrity failed'; end if;
end $$;
