#!/bin/bash

log_path="/var/log/$app"
log_file="$log_path/$app.log"

# Deploy the Django source tree (vendored in this repo under src/) into
# $install_dir, without dev-only artifacts.
myynh_deploy_source() {
	ynh_secure_remove --file="$install_dir/weddjango" 2>/dev/null || true
	mkdir -p "$install_dir"
	cp -a "$YNH_APP_BASEDIR/src/." "$install_dir/"
	ynh_safe_rm "$install_dir/db.sqlite3"
	ynh_safe_rm "$install_dir/.venv"
	ynh_safe_rm "$install_dir/.python-version"
	find "$install_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
}

# Create/refresh the venv at $install_dir/.venv from src/pyproject.toml + src/uv.lock,
# using uv (bootstrapped via pip since Debian's apt has no uv package).
myynh_setup_venv() {
	if [ ! -x "$install_dir/.venv/bin/uv" ]; then
		ynh_exec_as_app python3 -m venv "$install_dir/.venv"
	fi
	ynh_exec_as_app "$install_dir/.venv/bin/pip" install --quiet --upgrade pip uv
	ynh_exec_as_app env UV_PROJECT_ENVIRONMENT="$install_dir/.venv" \
		"$install_dir/.venv/bin/uv" sync --frozen --no-dev --project "$install_dir"
}

myynh_setup_log_file() {
	mkdir -p "$log_path"
	touch "$log_file"
	chown -R "$app:$app" "$log_path"
	chmod u+rwX,o-rwx "$log_path"
}

myynh_fix_file_permissions() {
	# /var/www/$app/ : static/media served by nginx, www-data needs read access
	chown -R "$app:www-data" "$install_dir"
	chmod u+rwX,g+rX,o-rwx "$install_dir"

	# /home/yunohost.app/$app/ : sqlite db + secret key, app-private
	chown -R "$app:$app" "$data_dir"
	chmod u+rwX,o-rwx "$data_dir"
}
