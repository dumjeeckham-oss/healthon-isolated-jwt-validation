create or replace function public.upsert_health_daily(p_user_id uuid,p_date date,p_steps integer,p_distance_km double precision,p_calories double precision,p_exercise_minutes integer,p_active_minutes integer)
returns uuid language plpgsql security definer as $$
declare result_id uuid;
begin
 if auth.uid() is null or p_user_id is distinct from auth.uid() then raise exception 'Unauthorized user' using errcode='42501'; end if;
 insert into public.health_daily(user_id,date,steps,distance_km,calories,exercise_minutes,active_minutes) values(p_user_id,p_date,p_steps,p_distance_km,p_calories,p_exercise_minutes,p_active_minutes)
 on conflict(user_id,date) do update set steps=excluded.steps,distance_km=excluded.distance_km,calories=excluded.calories,exercise_minutes=excluded.exercise_minutes,active_minutes=excluded.active_minutes,updated_at=now()
 returning id into result_id; return result_id;
end; $$;
grant execute on function public.upsert_health_daily(uuid,date,integer,double precision,double precision,integer,integer) to anon, authenticated;
